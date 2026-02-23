package com.example.mbtichatfriend.ui.components

import android.content.Context
import android.hardware.Sensor
import android.hardware.SensorEvent
import android.hardware.SensorEventListener
import android.hardware.SensorManager
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.State
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.platform.LocalContext

@Composable
fun rememberSensorState(sensitivity: Float = 0.6f): State<Offset> {
    val context = LocalContext.current
    val tiltState = remember { mutableStateOf(Offset.Zero) }

    DisposableEffect(Unit) {
        val sensorManager = context.getSystemService(Context.SENSOR_SERVICE) as? SensorManager
        val accelerometer = sensorManager?.getDefaultSensor(Sensor.TYPE_ACCELEROMETER)

        val listener = object : SensorEventListener {
            private var smoothX = 0f
            private var smoothY = 0f

            override fun onSensorChanged(event: SensorEvent) {
                val rawX = event.values[0].coerceIn(-4f, 4f)
                val rawY = event.values[1].coerceIn(-4f, 4f)
                smoothX += (rawX - smoothX) * 0.1f
                smoothY += (rawY - smoothY) * 0.1f
                tiltState.value = Offset(
                    x = -smoothX * sensitivity,
                    y = (smoothY - 5f) * sensitivity
                )
            }

            override fun onAccuracyChanged(sensor: Sensor?, accuracy: Int) {}
        }

        accelerometer?.let {
            sensorManager.registerListener(listener, it, SensorManager.SENSOR_DELAY_GAME)
        }

        onDispose {
            sensorManager?.unregisterListener(listener)
        }
    }

    return tiltState
}
