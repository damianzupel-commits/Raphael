package com.jarvisremote.app.ui.chat

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.jarvisremote.app.data.ChatMirrorClient
import com.jarvisremote.app.data.ChatRepository
import com.jarvisremote.app.data.SettingsRepository
import com.jarvisremote.app.data.describeError
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class ChatViewModel(application: Application) : AndroidViewModel(application) {
    private val settingsRepository = SettingsRepository(application)
    private val chatRepository = ChatRepository(settingsRepository)

    private val _messages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val messages: StateFlow<List<ChatMessage>> = _messages.asStateFlow()

    private val _isSending = MutableStateFlow(false)
    val isSending: StateFlow<Boolean> = _isSending.asStateFlow()

    // Espejado en vivo (2026-10-06): lo que se escribe desde la PC aparece acá al toque.
    // El backend no reenvía a este celular su propio eco (filtra por client_id).
    private val mirror = ChatMirrorClient(settingsRepository, viewModelScope) { role, content ->
        val r = if (role == "user") MessageRole.USER else MessageRole.ASSISTANT
        _messages.update { it + ChatMessage(role = r, text = content) }
    }

    init {
        mirror.start()
        // Cargar el historial compartido al abrir (incluye lo que se escribió desde la PC).
        viewModelScope.launch {
            chatRepository.loadHistory().onSuccess { history ->
                if (_messages.value.isEmpty() && history.isNotEmpty()) {
                    _messages.value = history.map { m ->
                        ChatMessage(
                            role = if (m.role == "user") MessageRole.USER else MessageRole.ASSISTANT,
                            text = m.content,
                        )
                    }
                }
            }
        }
    }

    override fun onCleared() {
        mirror.stop()
        super.onCleared()
    }

    fun sendMessage(text: String) {
        val trimmed = text.trim()
        if (trimmed.isEmpty() || _isSending.value) return

        _messages.update { it + ChatMessage(role = MessageRole.USER, text = trimmed) }
        _isSending.value = true

        viewModelScope.launch {
            chatRepository.sendMessage(trimmed)
                .onSuccess { response ->
                    _messages.update {
                        it + ChatMessage(
                            role = MessageRole.ASSISTANT,
                            text = response.reply.ifBlank { "(sin respuesta de texto)" },
                            toolCalls = response.toolCalls,
                        )
                    }
                }
                .onFailure { error ->
                    _messages.update {
                        it + ChatMessage(role = MessageRole.ASSISTANT, text = describeError(error), isError = true)
                    }
                }
            _isSending.value = false
        }
    }
}
