package com.jarvisremote.app.ui.mando

import android.net.Uri
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.jarvisremote.app.data.BackendUrlResolver
import com.jarvisremote.app.data.SettingsRepository
import kotlinx.coroutines.flow.first

/** Mapa de inteligencia (globo) embebido: carga /globo (que sirve el backend, con Three.js)
 *  en un WebView. La key va en la URL para autenticar /api/geo/points + /ws/geo. */
@Composable
fun GloboOverlay(onClose: () -> Unit) {
    val context = LocalContext.current
    var url by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        try {
            val repo = SettingsRepository(context.applicationContext)
            val s = repo.settingsFlow.first()
            if (s.backendUrl.isBlank() || s.apiKey.isBlank()) {
                error = "Configurá la conexión con la PC primero."
                return@LaunchedEffect
            }
            val resolved = BackendUrlResolver.resolve(
                backendUrl = s.backendUrl,
                lastKnownDirectUrl = s.lastKnownDirectUrl,
                onDirectUrlDiscovered = { repo.saveLastKnownDirectUrl(it) },
            ).trimEnd('/')
            url = "$resolved/globo?key=${Uri.encode(s.apiKey)}"
        } catch (e: Exception) {
            error = e.message ?: "No se pudo abrir el mapa"
        }
    }

    Box(
        Modifier
            .fillMaxSize()
            .background(Color(0xFF04060C)),
    ) {
        val u = url
        if (u != null) {
            AndroidView(
                modifier = Modifier.fillMaxSize(),
                factory = { ctx ->
                    WebView(ctx).apply {
                        settings.javaScriptEnabled = true
                        settings.domStorageEnabled = true
                        webViewClient = WebViewClient()
                        loadUrl(u)
                    }
                },
            )
        } else if (error != null) {
            Text(
                error ?: "",
                color = Color(0xFFFF6B6B),
                modifier = Modifier.align(Alignment.Center).padding(24.dp),
            )
        } else {
            CircularProgressIndicator(Modifier.align(Alignment.Center), color = Color(0xFF4FD6C9))
        }

        // Barra con cerrar.
        Row(
            Modifier
                .fillMaxWidth()
                .background(Color(0xCC070C15))
                .padding(horizontal = 16.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("MAPA DE INTELIGENCIA", color = Color(0xFFDFE9F5), fontSize = 13.sp)
            Box(Modifier.weight(1f))
            IconButton(onClick = onClose) {
                Icon(Icons.Default.Close, contentDescription = "Cerrar", tint = Color(0xFFDFE9F5))
            }
        }
    }
}
