package com.raphael.empresas;

import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

import androidx.annotation.NonNull;
import androidx.core.app.NotificationCompat;
import androidx.work.Constraints;
import androidx.work.ExistingPeriodicWorkPolicy;
import androidx.work.NetworkType;
import androidx.work.PeriodicWorkRequest;
import androidx.work.WorkManager;
import androidx.work.Worker;
import androidx.work.WorkerParameters;

import org.json.JSONArray;

import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Scanner;
import java.util.concurrent.TimeUnit;

/**
 * Cada ~15 minutos (el mínimo que permite Android) le pregunta al servidor si hay pendientes que esperan a la
 * dueña y, si hay algo nuevo, avisa en el celular. No usa Firebase ni servidores de terceros: habla solo con el
 * Raphael de la dueña. Si el servidor no está al alcance (fuera de casa sin túnel), simplemente reintenta después.
 */
public class AvisosWorker extends Worker {
    private static final String CANAL = "pendientes";
    private static final int NOTIFICACION = 7;

    public AvisosWorker(@NonNull Context contexto, @NonNull WorkerParameters params) {
        super(contexto, params);
    }

    static void programar(Context c) {
        Constraints red = new Constraints.Builder().setRequiredNetworkType(NetworkType.CONNECTED).build();
        PeriodicWorkRequest pedido = new PeriodicWorkRequest.Builder(AvisosWorker.class, 15, TimeUnit.MINUTES)
                .setConstraints(red).build();
        WorkManager.getInstance(c).enqueueUniquePeriodicWork("avisos", ExistingPeriodicWorkPolicy.UPDATE, pedido);
    }

    @NonNull
    @Override
    public Result doWork() {
        Context c = getApplicationContext();
        SharedPreferences prefs = c.getSharedPreferences(MainActivity.PREFS, Context.MODE_PRIVATE);
        String servidor = MainActivity.servidorDe(prefs);
        String token = prefs.getString("token", "");
        if (servidor.isEmpty() || token.isEmpty()) return Result.success();
        try {
            HttpURLConnection con = (HttpURLConnection) new URL(servidor + "/api/pendientes").openConnection();
            con.setRequestProperty("Authorization", "Bearer " + token);
            con.setConnectTimeout(8000);
            con.setReadTimeout(8000);
            if (con.getResponseCode() == 401) {                    // la sesión venció: se renueva al abrir la app
                prefs.edit().remove("token").apply();
                return Result.success();
            }
            String cuerpo;
            try (Scanner sc = new Scanner(con.getInputStream(), "UTF-8").useDelimiter("\\A")) {
                cuerpo = sc.hasNext() ? sc.next() : "[]";
            }
            int n = new JSONArray(cuerpo).length();
            int yaAvisados = prefs.getInt("avisados", 0);
            NotificationManager nm = (NotificationManager) c.getSystemService(Context.NOTIFICATION_SERVICE);
            if (n == 0) {
                nm.cancel(NOTIFICACION);
                prefs.edit().putInt("avisados", 0).apply();
            } else if (n > yaAvisados) {                           // solo avisamos cuando aparece algo nuevo
                avisar(c, nm, n);
                prefs.edit().putInt("avisados", n).apply();
            }
            return Result.success();
        } catch (Exception e) {
            return Result.retry();
        }
    }

    private void avisar(Context c, NotificationManager nm, int n) {
        if (nm.getNotificationChannel(CANAL) == null) {
            nm.createNotificationChannel(new NotificationChannel(CANAL, "Pendientes", NotificationManager.IMPORTANCE_DEFAULT));
        }
        Intent abrir = new Intent(c, MainActivity.class).setFlags(Intent.FLAG_ACTIVITY_NEW_TASK | Intent.FLAG_ACTIVITY_CLEAR_TOP);
        PendingIntent toque = PendingIntent.getActivity(c, 0, abrir, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        String texto = n == 1 ? "Hay 1 cosa esperando tu decisión." : "Hay " + n + " cosas esperando tu decisión.";
        nm.notify(NOTIFICACION, new NotificationCompat.Builder(c, CANAL)
                .setSmallIcon(R.drawable.ic_stat)
                .setContentTitle("Raphael")
                .setContentText(texto)
                .setContentIntent(toque)
                .setAutoCancel(true)
                .build());
    }
}
