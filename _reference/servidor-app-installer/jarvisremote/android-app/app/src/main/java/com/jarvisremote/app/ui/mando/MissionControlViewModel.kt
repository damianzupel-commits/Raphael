package com.jarvisremote.app.ui.mando

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jarvisremote.app.data.BrigadeMeta
import com.jarvisremote.app.data.BrigadeRuntime
import com.jarvisremote.app.data.MissionControlClient
import com.jarvisremote.app.data.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

/** Estado de UI del Centro de Mando: metadata de brigadas + su estado en vivo + el modelo
 *  del orquestador maestro + si el WebSocket está conectado. */
data class MissionControlUi(
    val brigades: List<BrigadeMeta> = emptyList(),
    val runtime: Map<String, BrigadeRuntime> = emptyMap(),
    val masterModel: String = "OPUS 5.5",
    val connected: Boolean = false,
)

class MissionControlViewModel(application: Application) : AndroidViewModel(application) {
    private val settingsRepository = SettingsRepository(application)

    private val _ui = MutableStateFlow(MissionControlUi())
    val ui: StateFlow<MissionControlUi> = _ui.asStateFlow()

    private val client = MissionControlClient(
        settingsRepository = settingsRepository,
        scope = viewModelScope,
        onSnapshot = { brigades, state, master ->
            _ui.update { it.copy(brigades = brigades, runtime = state, masterModel = master) }
        },
        onBrigade = { id, runtime ->
            _ui.update { it.copy(runtime = it.runtime + (id to runtime)) }
        },
        onConnectionChange = { connected ->
            _ui.update { it.copy(connected = connected) }
        },
    )

    init {
        client.start()
    }

    override fun onCleared() {
        client.stop()
        super.onCleared()
    }
}
