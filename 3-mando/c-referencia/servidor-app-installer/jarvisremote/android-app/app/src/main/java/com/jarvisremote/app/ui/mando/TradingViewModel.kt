package com.jarvisremote.app.ui.mando

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jarvisremote.app.data.SettingsRepository
import com.jarvisremote.app.data.TradingRepository
import com.jarvisremote.app.data.TradingSymbol
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

data class TradingUi(
    val symbols: List<TradingSymbol> = emptyList(),
    val loading: Boolean = true,
    val refreshing: Boolean = false,
    val error: String? = null,
)

class TradingViewModel(application: Application) : AndroidViewModel(application) {
    private val repo = TradingRepository(SettingsRepository(application))

    private val _ui = MutableStateFlow(TradingUi())
    val ui: StateFlow<TradingUi> = _ui.asStateFlow()

    init {
        load()
    }

    fun load() {
        _ui.update { it.copy(loading = true, error = null) }
        viewModelScope.launch {
            repo.load()
                .onSuccess { s -> _ui.update { it.copy(symbols = s, loading = false) } }
                .onFailure { e -> _ui.update { it.copy(loading = false, error = e.message ?: "Sin conexión") } }
        }
    }

    fun add(instrument: String) {
        if (instrument.isBlank()) return
        viewModelScope.launch {
            repo.add(instrument).onSuccess { s -> _ui.update { it.copy(symbols = s) } }
        }
    }

    fun remove(instrument: String) {
        viewModelScope.launch {
            repo.remove(instrument).onSuccess { s -> _ui.update { it.copy(symbols = s) } }
        }
    }

    fun refresh() {
        _ui.update { it.copy(refreshing = true, error = null) }
        viewModelScope.launch {
            repo.refresh()
                .onSuccess { s -> _ui.update { it.copy(symbols = s, refreshing = false) } }
                .onFailure { e -> _ui.update { it.copy(refreshing = false, error = e.message ?: "Error al actualizar") } }
        }
    }

    fun backtest(instrument: String) {
        viewModelScope.launch {
            // El backend persiste el win_rate en el estado del símbolo; recargamos para mostrarlo.
            repo.backtest(instrument).onSuccess { load() }
        }
    }
}
