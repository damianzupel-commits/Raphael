package com.jarvisremote.app.ui.mando

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jarvisremote.app.data.IngestItem
import com.jarvisremote.app.data.IngestRepository
import com.jarvisremote.app.data.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class IngestUi(
    val sources: List<String> = emptyList(),
    val recent: List<IngestItem> = emptyList(),
    val loading: Boolean = true,
    val error: String? = null,
)

class IngestViewModel(application: Application) : AndroidViewModel(application) {
    private val repo = IngestRepository(SettingsRepository(application))

    private val _ui = MutableStateFlow(IngestUi())
    val ui: StateFlow<IngestUi> = _ui.asStateFlow()

    init {
        load()
    }

    fun load() {
        _ui.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            repo.load()
                .onSuccess { r -> _ui.update { it.copy(sources = r.sources, recent = r.recent, loading = false) } }
                .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message ?: "Sin conexión") } }
        }
    }

    fun addSource(url: String) {
        if (url.isBlank()) return
        viewModelScope.launch {
            repo.addSource(url).onSuccess { sources -> _ui.update { it.copy(sources = sources) } }
        }
    }

    fun removeSource(url: String) {
        viewModelScope.launch {
            repo.removeSource(url).onSuccess { sources -> _ui.update { it.copy(sources = sources) } }
        }
    }
}
