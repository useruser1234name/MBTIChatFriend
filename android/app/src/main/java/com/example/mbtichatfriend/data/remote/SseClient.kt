package com.example.mbtichatfriend.data.remote

import kotlinx.coroutines.channels.awaitClose
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.callbackFlow
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.sse.EventSource
import okhttp3.sse.EventSourceListener
import okhttp3.sse.EventSources
import com.example.mbtichatfriend.BuildConfig
import org.json.JSONObject
import javax.inject.Inject
import javax.inject.Singleton

sealed class SseEvent {
    data class Message(
        val text: String,
        val emotion: String,
        val delay: Long
    ) : SseEvent()

    data class Done(
        val affinityDelta: Int,
        val nightDiaryGenerated: Boolean = false,
        val nextHook: String = "",
        val nextGoal: String = "",
        val roomId: String = ""
    ) : SseEvent()
    data class Error(val message: String) : SseEvent()

    /**
     * R3: SSE 연결이 실제로 수립된 시점(EventSourceListener.onOpen).
     * "캐릭터가 메시지를 읽었다"의 근사치로 사용 — 읽음 처리는 이 이벤트 수신 즉시 이뤄져야 하며
     * 첫 토큰/버블 도착까지 기다리지 않는다(읽음 지연 금지).
     */
    object Opened : SseEvent()
}

@Singleton
class SseClient @Inject constructor(
    private val client: OkHttpClient
) {
    private val baseUrl = BuildConfig.BASE_URL.trimEnd('/')

    fun streamChat(request: ChatRequest): Flow<SseEvent> = callbackFlow {
        val json = JSONObject().apply {
            put("message", request.message)
            put("mbti", request.mbti)
            put("speech_style", request.speechStyle)
            put("relationship", request.relationship)
            put("nickname", request.nickname)
            put("affinity_level", request.affinityLevel)
            val historyArray = org.json.JSONArray()
            request.conversationHistory.forEach { map ->
                val obj = JSONObject()
                map.forEach { (k, v) -> obj.put(k, v) }
                historyArray.put(obj)
            }
            put("conversation_history", historyArray)
            request.userMbti?.let { put("user_mbti", it) }
            if (request.characterName.isNotEmpty()) {
                put("character_name", request.characterName)
            }
            if (request.characterId.isNotEmpty()) {
                put("character_id", request.characterId)
            }
            if (request.memories.isNotEmpty()) {
                val memoriesArray = org.json.JSONArray()
                request.memories.forEach { item ->
                    val memObj = JSONObject()
                    memObj.put("key", item.key)
                    memObj.put("value", item.value)
                    memoriesArray.put(memObj)
                }
                put("memories", memoriesArray)
            }
        }

        val body = json.toString().toRequestBody("application/json".toMediaType())
        val httpRequest = Request.Builder()
            .url("$baseUrl/api/v1/chat/stream")
            .post(body)
            .header("Accept", "text/event-stream")
            .build()

        val listener = object : EventSourceListener() {
            override fun onOpen(eventSource: EventSource, response: okhttp3.Response) {
                // R3: 연결 수립 = 읽음. 지연 없이 즉시 방출한다.
                trySend(SseEvent.Opened)
            }

            override fun onEvent(
                eventSource: EventSource,
                id: String?,
                type: String?,
                data: String
            ) {
                try {
                    when (type) {
                        "message" -> {
                            val obj = JSONObject(data)
                            trySend(
                                SseEvent.Message(
                                    text = obj.getString("text"),
                                    emotion = obj.optString("emotion", "NEUTRAL"),
                                    delay = obj.optLong("delay", 500)
                                )
                            )
                        }
                        "done" -> {
                            val obj = JSONObject(data)
                            trySend(SseEvent.Done(
                                affinityDelta = obj.optInt("affinity_delta", 0),
                                nightDiaryGenerated = obj.optBoolean("night_diary_generated", false),
                                nextHook = obj.optString("next_hook", ""),
                                nextGoal = obj.optString("next_goal", ""),
                                roomId = obj.optString("room_id", "")
                            ))
                            close()
                        }
                    }
                } catch (e: Exception) {
                    trySend(SseEvent.Error(e.message ?: "파싱 오류"))
                }
            }

            override fun onFailure(
                eventSource: EventSource,
                t: Throwable?,
                response: okhttp3.Response?
            ) {
                trySend(SseEvent.Error(t?.message ?: "연결 실패"))
                close()
            }

            override fun onClosed(eventSource: EventSource) {
                close()
            }
        }

        val factory = EventSources.createFactory(client)
        val eventSource = factory.newEventSource(httpRequest, listener)

        awaitClose {
            eventSource.cancel()
        }
    }
}
