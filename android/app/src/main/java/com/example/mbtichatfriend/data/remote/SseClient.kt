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

    /**
     * /chat/stream 과 /chat/proactive가 공유하는 필드를 JSONObject에 채운다.
     * 차이는 message(전자) vs hook(후자) 하나뿐이므로 호출부에서 그 필드만 추가로 put한다.
     */
    private fun putCommonFields(
        json: JSONObject,
        mbti: String,
        speechStyle: String,
        relationship: String,
        nickname: String,
        affinityLevel: Int,
        conversationHistory: List<Map<String, String>>,
        userMbti: String?,
        characterName: String,
        characterId: String,
        memories: List<MemoryItem>,
        userRole: String,
        situation: String,
    ) {
        json.apply {
            put("mbti", mbti)
            put("speech_style", speechStyle)
            put("relationship", relationship)
            put("nickname", nickname)
            put("affinity_level", affinityLevel)
            val historyArray = org.json.JSONArray()
            conversationHistory.forEach { map ->
                val obj = JSONObject()
                map.forEach { (k, v) -> obj.put(k, v) }
                historyArray.put(obj)
            }
            put("conversation_history", historyArray)
            userMbti?.let { put("user_mbti", it) }
            if (characterName.isNotEmpty()) {
                put("character_name", characterName)
            }
            if (characterId.isNotEmpty()) {
                put("character_id", characterId)
            }
            if (memories.isNotEmpty()) {
                val memoriesArray = org.json.JSONArray()
                memories.forEach { item ->
                    val memObj = JSONObject()
                    memObj.put("key", item.key)
                    memObj.put("value", item.value)
                    memoriesArray.put(memObj)
                }
                put("memories", memoriesArray)
            }
            // M2: "내 역할"/"지금 상황" — 빈 문자열이어도 항상 포함(서버가 빈 값을 무시)
            put("user_role", userRole)
            put("situation", situation)
        }
    }

    fun streamChat(request: ChatRequest): Flow<SseEvent> {
        val json = JSONObject().apply { put("message", request.message) }
        putCommonFields(
            json = json,
            mbti = request.mbti,
            speechStyle = request.speechStyle,
            relationship = request.relationship,
            nickname = request.nickname,
            affinityLevel = request.affinityLevel,
            conversationHistory = request.conversationHistory,
            userMbti = request.userMbti,
            characterName = request.characterName,
            characterId = request.characterId,
            memories = request.memories,
            userRole = request.userRole,
            situation = request.situation,
        )
        return openStream("$baseUrl/api/v1/chat/stream", json)
    }

    /**
     * R1: 선톡(캐릭터 선발화) 전용 스트림. /chat/proactive는 /chat/stream과 SSE 이벤트
     * 계약이 동일하다(message×N → done). message 대신 hook을 보내며, 서버가
     * 유도 문구 합성·유저 메시지 미적재·호감도 미반영(affinity_delta=0)을 책임진다.
     */
    fun streamProactive(request: ProactiveChatRequest): Flow<SseEvent> {
        val json = JSONObject().apply { put("hook", request.hook) }
        putCommonFields(
            json = json,
            mbti = request.mbti,
            speechStyle = request.speechStyle,
            relationship = request.relationship,
            nickname = request.nickname,
            affinityLevel = request.affinityLevel,
            conversationHistory = request.conversationHistory,
            userMbti = request.userMbti,
            characterName = request.characterName,
            characterId = request.characterId,
            memories = request.memories,
            userRole = request.userRole,
            situation = request.situation,
        )
        return openStream("$baseUrl/api/v1/chat/proactive", json)
    }

    private fun openStream(url: String, json: JSONObject): Flow<SseEvent> = callbackFlow {
        val body = json.toString().toRequestBody("application/json".toMediaType())
        val httpRequest = Request.Builder()
            .url(url)
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
