package com.raphael.empresas;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.FrameLayout;

import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowCompat;
import androidx.core.view.WindowInsetsCompat;

import org.json.JSONObject;

import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Scanner;

/**
 * Raphael Empresas para el celular: la app nativa de la dueña.
 *
 * Es una ventana (WebView) al panel de SU Raphael, el que corre en la mini PC del negocio. La primera vez
 * pide la dirección del servidor; después abre directo. Suma lo que una página web no puede: instalarse con
 * su ícono, avisar en el celular cuando hay algo pendiente y subir fotos y videos desde la galería.
 */
public class MainActivity extends Activity {
    static final String PREFS = "raphael";
    static final String ASSET_CONECTAR = "file:///android_asset/conectar.html";
    static final String ASSET_SIN_CONEXION = "file:///android_asset/sin-conexion.html";
    private static final int PEDIR_ARCHIVO = 41;
    private static final int PEDIR_NOTIFICACIONES = 42;

    private WebView web;
    private SharedPreferences prefs;
    private ValueCallback<Uri[]> subida;
    private volatile String paginaActual = "";

    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);

        FrameLayout raiz = new FrameLayout(this);
        raiz.setBackgroundColor(getColor(R.color.fondo));
        web = new WebView(this);
        web.setBackgroundColor(getColor(R.color.fondo));
        raiz.addView(web, new FrameLayout.LayoutParams(-1, -1));
        setContentView(raiz);

        // Dibujamos bajo las barras del sistema (obligatorio desde Android 15): dejamos el margen nosotros.
        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        WindowCompat.getInsetsController(getWindow(), raiz).setAppearanceLightStatusBars(false);
        ViewCompat.setOnApplyWindowInsetsListener(raiz, (v, insets) -> {
            Insets b = insets.getInsets(WindowInsetsCompat.Type.systemBars() | WindowInsetsCompat.Type.ime());
            v.setPadding(b.left, b.top, b.right, b.bottom);
            return WindowInsetsCompat.CONSUMED;
        });

        configurarWeb();
        pedirPermisoDeAvisos();

        if (estado != null) {
            web.restoreState(estado);
        } else {
            abrirInicio();
        }
        AvisosWorker.programar(this);
    }

    private void configurarWeb() {
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setMediaPlaybackRequiresUserGesture(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE);
        s.setUserAgentString(s.getUserAgentString() + " RaphaelEmpresasApp/" + version());
        web.addJavascriptInterface(new Puente(), "RaphaelApp");

        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView v, WebResourceRequest req) {
                String url = req.getUrl().toString();
                if (url.startsWith("file:///android_asset/") || esDelServidor(url)) return false;
                // Cualquier otro sitio (la tienda web, Instagram…) se abre afuera, nunca dentro de la app.
                try {
                    startActivity(new Intent(Intent.ACTION_VIEW, req.getUrl()));
                } catch (Exception ignorado) { /* sin app para abrirlo */ }
                return true;
            }

            @Override
            public void onPageStarted(WebView v, String url, Bitmap icono) {
                paginaActual = url;
            }

            @Override
            public void onReceivedError(WebView v, WebResourceRequest req, WebResourceError err) {
                if (req.isForMainFrame() && !req.getUrl().toString().startsWith("file:")) {
                    v.loadUrl(ASSET_SIN_CONEXION);
                }
            }
        });

        web.setWebChromeClient(new WebChromeClient() {
            @Override
            public boolean onShowFileChooser(WebView v, ValueCallback<Uri[]> cb, FileChooserParams params) {
                if (subida != null) subida.onReceiveValue(null);
                subida = cb;
                try {
                    startActivityForResult(params.createIntent(), PEDIR_ARCHIVO);
                } catch (Exception e) {
                    subida = null;
                    return false;
                }
                return true;
            }
        });

        web.setDownloadListener((url, ua, disp, mime, largo) -> {
            try {
                startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(url)));
            } catch (Exception ignorado) { /* nada */ }
        });
    }

    // ------------------------------------------------------------------ navegación
    /** La dirección fija con la que se compiló la app (nube) o, si no hay, la que escribió la dueña (red local). */
    static String servidorDe(SharedPreferences prefs) {
        return BuildConfig.SERVIDOR_FIJO.isEmpty() ? prefs.getString("servidor", "") : BuildConfig.SERVIDOR_FIJO;
    }

    private String servidor() {
        return servidorDe(prefs);
    }

    private void abrirInicio() {
        String s = servidor();
        web.loadUrl(s.isEmpty() ? ASSET_CONECTAR : s + "/panel/");
    }

    private boolean esDelServidor(String url) {
        String s = servidor();
        return !s.isEmpty() && url.startsWith(s);
    }

    /** Solo las páginas de la propia app o de tu servidor pueden usar el puente. */
    private boolean paginaDeConfianza() {
        String p = paginaActual;
        return p.startsWith("file:///android_asset/") || esDelServidor(p);
    }

    private static String normalizar(String texto) {
        String u = texto == null ? "" : texto.trim();
        if (u.isEmpty()) return "";
        if (!u.matches("(?i)^https?://.*")) u = "http://" + u;
        u = u.replaceAll("(?i)/(panel|app)(/.*)?$", "").replaceAll("/+$", "");
        return u;
    }

    private String version() {
        try {
            return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
        } catch (Exception e) {
            return "?";
        }
    }

    private void pedirPermisoDeAvisos() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, PEDIR_NOTIFICACIONES);
        }
    }

    // ------------------------------------------------------------------ lo que las páginas pueden pedirle a la app
    private class Puente {
        @JavascriptInterface
        public String servidor() {
            return paginaDeConfianza() ? MainActivity.this.servidor() : "";
        }

        @JavascriptInterface
        public String version() {
            return MainActivity.this.version();
        }

        /** Verifica que en esa dirección haya un Raphael y le contesta a conectar.html. */
        @JavascriptInterface
        public void probar(String direccion) {
            if (!paginaDeConfianza()) return;
            final String url = normalizar(direccion);
            new Thread(() -> {
                String resultado;
                try {
                    HttpURLConnection c = (HttpURLConnection) new URL(url + "/salud").openConnection();
                    c.setConnectTimeout(6000);
                    c.setReadTimeout(6000);
                    String cuerpo;
                    try (Scanner sc = new Scanner(c.getInputStream(), "UTF-8").useDelimiter("\\A")) {
                        cuerpo = sc.hasNext() ? sc.next() : "";
                    }
                    JSONObject j = new JSONObject(cuerpo);
                    if (!j.optBoolean("ok")) throw new IllegalStateException("no es Raphael");
                    resultado = new JSONObject().put("ok", true).put("url", url).put("version", j.optString("version")).toString();
                } catch (Exception e) {
                    String msg = e instanceof java.net.UnknownHostException || e instanceof java.net.ConnectException || e instanceof java.net.SocketTimeoutException
                            ? "No pude llegar a esa dirección. ¿La PC con Raphael está prendida y el celular en el mismo wifi?"
                            : "Esa dirección responde, pero no parece ser un Raphael.";
                    try {
                        resultado = new JSONObject().put("ok", false).put("error", msg).toString();
                    } catch (Exception x) {
                        resultado = "{\"ok\":false}";
                    }
                }
                final String r = resultado;
                runOnUiThread(() -> web.evaluateJavascript("conectarResultado(" + r + ")", null));
            }).start();
        }

        @JavascriptInterface
        public void guardar(String direccion) {
            if (!paginaDeConfianza()) return;
            final String url = normalizar(direccion);
            if (url.isEmpty()) return;
            prefs.edit().putString("servidor", url).apply();
            runOnUiThread(MainActivity.this::abrirInicio);
        }

        /** El panel nos pasa su sesión para que los avisos en segundo plano puedan consultar los pendientes. */
        @JavascriptInterface
        public void guardarToken(String token) {
            if (!paginaDeConfianza()) return;
            prefs.edit().putString("token", token == null ? "" : token).apply();
            AvisosWorker.programar(MainActivity.this);
        }

        /** true si la app viene con el servidor incluido (no hay nada que cambiar). */
        @JavascriptInterface
        public boolean fijo() {
            return !BuildConfig.SERVIDOR_FIJO.isEmpty();
        }

        @JavascriptInterface
        public void cambiarServidor() {
            if (!paginaDeConfianza() || !BuildConfig.SERVIDOR_FIJO.isEmpty()) return;
            prefs.edit().remove("servidor").remove("token").remove("avisados").apply();
            runOnUiThread(() -> {
                web.clearHistory();
                web.loadUrl(ASSET_CONECTAR);
            });
        }

        @JavascriptInterface
        public void reintentar() {
            if (!paginaDeConfianza()) return;
            runOnUiThread(MainActivity.this::abrirInicio);
        }
    }

    // ------------------------------------------------------------------ ciclo de vida
    @Override
    protected void onActivityResult(int pedido, int resultado, Intent datos) {
        if (pedido == PEDIR_ARCHIVO && subida != null) {
            subida.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(resultado, datos));
            subida = null;
            return;
        }
        super.onActivityResult(pedido, resultado, datos);
    }

    @Override
    protected void onSaveInstanceState(Bundle estado) {
        super.onSaveInstanceState(estado);
        web.saveState(estado);
    }

    @Override
    protected void onResume() {
        super.onResume();
        web.onResume();
        web.setVisibility(View.VISIBLE);
    }

    @Override
    protected void onPause() {
        web.onPause();
        super.onPause();
    }

    @Override
    @SuppressWarnings("deprecation")
    public void onBackPressed() {
        if (web.canGoBack() && !paginaActual.startsWith("file:")) {
            web.goBack();
        } else {
            moveTaskToBack(true);        // no cerramos la app: sigue lista para los avisos
        }
    }

    @Override
    protected void onDestroy() {
        web.destroy();
        super.onDestroy();
    }
}
