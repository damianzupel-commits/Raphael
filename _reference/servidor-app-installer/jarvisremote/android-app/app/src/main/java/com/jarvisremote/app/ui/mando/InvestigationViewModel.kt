package com.jarvisremote.app.ui.mando

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jarvisremote.app.data.InvestigationRepository
import com.jarvisremote.app.data.ResearchCase
import com.jarvisremote.app.data.SettingsRepository
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class InvestigationUi(
    val cases: List<ResearchCase> = emptyList(),
    val loading: Boolean = true,
    val error: String? = null,
)

class InvestigationViewModel(application: Application) : AndroidViewModel(application) {
    private val repo = InvestigationRepository(SettingsRepository(application))

    private val _ui = MutableStateFlow(InvestigationUi())
    val ui: StateFlow<InvestigationUi> = _ui.asStateFlow()

    init {
        load()
    }

    fun load() {
        _ui.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            repo.load()
                .onSuccess { cases -> _ui.update { it.copy(cases = cases, loading = false) } }
                .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message ?: "Sin conexión") } }
        }
    }

    fun setStatus(id: String, status: String) {
        viewModelScope.launch {
            repo.setStatus(id, status).onSuccess { cases -> _ui.update { it.copy(cases = cases) } }
        }
    }
}
