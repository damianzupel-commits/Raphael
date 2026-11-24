package com.jarvisremote.app.ui.chat

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Send
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.animation.core.LinearEasing
import kotlin.math.abs
import kotlin.math.sin
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import com.jarvisremote.app.data.ToolCallLog

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ChatScreen(
    onOpenSettings: () -> Unit,
    onOpenMando: () -> Unit = {},
    viewModel: ChatViewModel = viewModel(),
) {
    val messages by viewModel.messages.collectAsState()
    val isSending by viewModel.isSending.collectAsState()
    var input by rememberSaveable { mutableStateOf("") }

    val listState = rememberLazyListState()

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        // Avatar de estado (2026-10-07, pedido por el propio Raphael): late
                        // tranquilo cuando está inactivo y más vivo/rápido mientras piensa.
                        RaphaelAvatar(thinking = isSending)
                        Spacer(Modifier.width(10.dp))
                        Text("Raphael")
                    }
                },
                actions = {
                    IconButton(onClick = onOpenMando) {
                        Icon(Icons.Default.Dashboard, contentDescription = "Centro de Mando")
                    }
                    IconButton(onClick = onOpenSettings) {
                        Icon(Icons.Default.Settings, contentDescription = "Configuración")
                    }
                },
            )
        },
        bottomBar = {
            ChatInputBar(
                value = input,
                onValueChange = { input = it },
                enabled = !isSending,
                onSend = {
                    if (input.isNotBlank()) {
                        viewModel.sendMessage(input)
                        input = ""
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            state = listState,
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
            contentPadding = PaddingValues(vertical = 12.dp),
        ) {
            items(messages, key = { it.id }) { message ->
                ChatBubble(message)
            }
            if (isSending) {
                item { TypingIndicator() }
            }
        }
    }
}

@Composable
private fun ChatInputBar(
    value: String,
    onValueChange: (String) -> Unit,
    enabled: Boolean,
    onSend: () -> Unit,
) {
    Surface(tonalElevation = 3.dp) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = value,
                onValueChange = onValueChange,
                modifier = Modifier.weight(1f),
                placeholder = { Text("Decile algo a Raphael...") },
                enabled = enabled,
                maxLines = 4,
            )
            Spacer(Modifier.width(8.dp))
            IconButton(onClick = onSend, enabled = enabled && value.isNotBlank()) {
                Icon(Icons.Default.Send, contentDescription = "Enviar")
            }
        }
    }
}

@Composable
private fun TypingIndicator() {
    Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(4.dp)) {
        CircularProgressIndicator(modifier = Modifier.size(16.dp), strokeWidth = 2.dp)
        Spacer(Modifier.width(8.dp))
        Text("Raphael está pensando...", style = MaterialTheme.typography.bodySmall)
    }
}

@Composable
private fun ChatBubble(message: ChatMessage) {
    val isUser = message.role == MessageRole.USER
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start,
    ) {
        val bubbleColor = when {
            message.isError -> MaterialTheme.colorScheme.errorContainer
            isUser -> MaterialTheme.colorScheme.primaryContainer
            else -> MaterialTheme.colorScheme.surfaceVariant
        }
        Surface(
            color = bubbleColor,
            shape = RoundedCornerShape(
                topStart = 16.dp,
                topEnd = 16.dp,
                bottomStart = if (isUser) 16.dp else 4.dp,
                bottomEnd = if (isUser) 4.dp else 16.dp,
            ),
        ) {
            Text(
                text = message.text,
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                style = MaterialTheme.typography.bodyMedium,
            )
        }
        if (message.toolCalls.isNotEmpty()) {
            Spacer(Modifier.height(4.dp))
            ToolCallsSection(message.toolCalls)
        }
    }
}

/**
 * Avatar de Raphael — núcleo de la Gran Sabia (2026-10-13, estética Tensura, misma
 * que el orbe del Centro de Mando en la PC). Un núcleo radiante blanco→dorado→cian→violeta
 * que "respira", rodeado por 3 anillos orbitales que tumban en planos distintos para
 * simular el giroscopio 3D. Inactivo gira lento y tenue; mientras piensa (`thinking`) gira
 * más rápido y brilla más. Dibujado con Canvas + animación infinita, sin assets.
 */
@Composable
fun RaphaelAvatar(thinking: Boolean, modifier: Modifier = Modifier, diameter: Dp = 26.dp) {
    val transition = rememberInfiniteTransition(label = "sage")
    // Giro continuo (0→360) que alimenta la rotación de los anillos.
    val spin by transition.animateFloat(
        initialValue = 0f,
        targetValue = 360f,
        animationSpec = infiniteRepeatable(
            animation = tween(if (thinking) 2600 else 6200, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "spin",
    )
    // Latido del núcleo.
    val pulse by transition.animateFloat(
        initialValue = 0.90f,
        targetValue = 1.06f,
        animationSpec = infiniteRepeatable(
            animation = tween(if (thinking) 720 else 1900, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "pulse",
    )
    val cyan = Color(0xFF59E0FF)
    val violet = Color(0xFF7A4FFF)
    val gold = Color(0xFFFFE9B0)
    Canvas(modifier = modifier.size(diameter)) {
        val c = center
        val maxR = size.minDimension / 2f
        // Halo suave (cian + violeta) que respira.
        drawCircle(color = cyan.copy(alpha = if (thinking) 0.22f else 0.15f), radius = maxR * pulse, center = c)
        drawCircle(color = violet.copy(alpha = 0.13f), radius = maxR * 0.82f * pulse, center = c)
        // Núcleo radiante: blanco → dorado → cian → violeta → transparente.
        val coreR = maxR * 0.46f * pulse
        drawCircle(
            brush = Brush.radialGradient(
                colorStops = arrayOf(
                    0.00f to Color.White,
                    0.20f to gold,
                    0.55f to cyan,
                    0.85f to violet,
                    1.00f to Color.Transparent,
                ),
                center = c,
                radius = coreR,
            ),
            radius = coreR,
            center = c,
        )
        // 3 anillos orbitales: (radio horizontal, color, inclinación base del plano).
        val rings = listOf(
            Triple(maxR * 0.70f, cyan, 0f),
            Triple(maxR * 0.86f, violet, 60f),
            Triple(maxR * 1.00f, gold, 120f),
        )
        val stroke = Stroke(width = maxR * 0.07f)
        rings.forEachIndexed { i, (rr, col, tilt) ->
            // El "tumbo" 3D: la altura del óvalo late de casi-línea (de canto) a círculo (de frente).
            val phase = Math.toRadians((spin * (1f + i * 0.45f) + i * 90f).toDouble())
            val hy = (rr * abs(sin(phase)).toFloat()).coerceAtLeast(rr * 0.12f)
            val planeSpin = tilt + spin * (if (i % 2 == 0) 0.35f else -0.35f)
            rotate(degrees = planeSpin, pivot = c) {
                drawOval(
                    color = col.copy(alpha = 0.85f),
                    topLeft = Offset(c.x - rr, c.y - hy),
                    size = Size(rr * 2f, hy * 2f),
                    style = stroke,
                )
            }
        }
    }
}

@Composable
private fun ToolCallsSection(toolCalls: List<ToolCallLog>) {
    var expanded by rememberSaveable { mutableStateOf(false) }
    Column {
        TextButton(onClick = { expanded = !expanded }) {
            Text(
                if (expanded) {
                    "Ocultar herramientas usadas (${toolCalls.size})"
                } else {
                    "Ver herramientas usadas (${toolCalls.size})"
                },
            )
        }
        if (expanded) {
            toolCalls.forEach { tc ->
                Surface(
                    color = MaterialTheme.colorScheme.surface,
                    shape = RoundedCornerShape(8.dp),
                    tonalElevation = 1.dp,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 2.dp),
                ) {
                    Column(modifier = Modifier.padding(8.dp)) {
                        Text(tc.tool, style = MaterialTheme.typography.labelLarge)
                        Text(
                            "args: ${tc.arguments}",
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                        )
                        Text(
                            "result: ${tc.result}",
                            style = MaterialTheme.typography.bodySmall,
                            fontFamily = FontFamily.Monospace,
                        )
                    }
                }
            }
        }
    }
}
