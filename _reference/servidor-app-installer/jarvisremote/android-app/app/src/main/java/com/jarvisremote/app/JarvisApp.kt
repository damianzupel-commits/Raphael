package com.jarvisremote.app

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Surface
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.rememberNavController
import com.jarvisremote.app.data.SettingsRepository
import com.jarvisremote.app.ui.chat.ChatScreen
import com.jarvisremote.app.ui.mando.MissionControlScreen
import com.jarvisremote.app.ui.pairing.PairScanScreen
import com.jarvisremote.app.ui.settings.SettingsScreen
import kotlinx.coroutines.flow.map

private object Routes {
    const val SETTINGS = "settings"
    const val CHAT = "chat"
    const val MANDO = "mando"
    const val PAIR = "pair"
}

@Composable
fun JarvisApp() {
    val context = LocalContext.current
    val settingsRepository = remember { SettingsRepository(context) }
    val isConfigured by remember {
        settingsRepository.settingsFlow.map { it.backendUrl.isNotBlank() && it.apiKey.isNotBlank() }
    }.collectAsState(initial = null)

    Surface(modifier = Modifier.fillMaxSize()) {
        val configured = isConfigured
        if (configured == null) {
            // Todavía leyendo la config guardada en DataStore.
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
        } else {
            val navController = rememberNavController()
            NavHost(
                navController = navController,
                startDestination = if (configured) Routes.CHAT else Routes.SETTINGS,
            ) {
                composable(Routes.SETTINGS) {
                    SettingsScreen(
                        onSaved = {
                            navController.navigate(Routes.CHAT) {
                                popUpTo(Routes.SETTINGS) { inclusive = true }
                            }
                        },
                        onScanQr = { navController.navigate(Routes.PAIR) },
                    )
                }
                composable(Routes.PAIR) {
                    PairScanScreen(
                        onPaired = {
                            navController.navigate(Routes.CHAT) {
                                popUpTo(Routes.SETTINGS) { inclusive = true }
                            }
                        },
                        onCancel = { navController.popBackStack() },
                    )
                }
                composable(Routes.CHAT) {
                    ChatScreen(
                        onOpenSettings = { navController.navigate(Routes.SETTINGS) },
                        onOpenMando = { navController.navigate(Routes.MANDO) },
                    )
                }
                composable(Routes.MANDO) {
                    MissionControlScreen(onBack = { navController.popBackStack() })
                }
            }
        }
    }
}
