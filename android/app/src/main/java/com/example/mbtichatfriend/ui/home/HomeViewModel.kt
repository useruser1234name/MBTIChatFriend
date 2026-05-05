package com.example.mbtichatfriend.ui.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.local.CharacterEntity
import com.example.mbtichatfriend.data.local.MessageDao
import com.example.mbtichatfriend.data.local.UserPreferences
import com.example.mbtichatfriend.data.remote.ChatApi
import com.example.mbtichatfriend.data.remote.ImageSetRequest
import com.example.mbtichatfriend.data.remote.TrendingPostUi
import com.example.mbtichatfriend.data.repository.CharacterRepository
import com.example.mbtichatfriend.ui.community.CommunityPostUi
import com.example.mbtichatfriend.ui.community.toUi
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalDate
import javax.inject.Inject

data class LastMessageInfo(
    val text: String,
    val timestamp: Long,
    val isFromUser: Boolean
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val characterRepo: CharacterRepository,
    private val messageDao: MessageDao,
    private val prefs: UserPreferences,
    val chatApi: ChatApi
) : ViewModel() {

    val characters = characterRepo.observeAll()
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    val nickname = prefs.nickname
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    val userMbti = prefs.userMbti
        .stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), "")

    private val _lastMessages = MutableStateFlow<Map<Long, LastMessageInfo>>(emptyMap())
    val lastMessages = _lastMessages.asStateFlow()

    private val _trendingPosts = MutableStateFlow<List<TrendingPostUi>>(emptyList())

    private val _eventTrendingPosts = MutableStateFlow<List<CommunityPostUi>>(emptyList())
    val eventTrendingPosts: StateFlow<List<CommunityPostUi>> = _eventTrendingPosts.asStateFlow()

    // MVI 통합 UiState
    private val _uiState = MutableStateFlow<HomeUiState>(HomeUiState.Loading)
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    private fun syncHomeUiState() {
        viewModelScope.launch {
            try {
                _uiState.value = HomeUiState.Loading
                val openBeta = showOpenBetaBanner()
                val dau10k = showDau10kBanner()
                val newYearCard = showNewYearCard()
                val whiteDay = showWhiteDayBanner()
                val gratitudeCard = showGratitudeCardBanner()
                val lora8Banner = showLora8Banner()
                val gratitudeTeaser = showGratitudeTeaserBanner()
                val lora9Banner = showLora9Banner()
                val childrenDay = showChildrenDayCard()
                val esfp10Banner = showEsfp10Banner()
                val entj11Banner = showEntj11Banner()
                val istj12Banner = showIstj12Banner()
                val estp13Banner = showEstp13Banner()
                val summerCard = showSummerCard()
                val enfj14Banner = showEnfj14Banner()
                val allMbtiBanner = showAllMbtiBanner()
                combine(characters, _lastMessages, _trendingPosts, _eventTrendingPosts) { chars, _, trending, eventTrending ->
                    HomeUiState.Success(
                        characters = chars,
                        selectedCharacter = chars.firstOrNull(),
                        openBetaBanner = openBeta,
                        dau10kBanner = dau10k,
                        trendingPosts = trending,
                        showNewYearCard = newYearCard,
                        showWhiteDay = whiteDay,
                        showGratitudeCard = gratitudeCard,
                        showLora8Banner = lora8Banner,
                        showGratitudeTeaser = gratitudeTeaser,
                        showLora9Banner = lora9Banner,
                        eventTrendingPosts = eventTrending,
                        showChildrenDay = childrenDay,
                        showEsfp10Banner = esfp10Banner,
                        showEntj11Banner = entj11Banner,
                        showIstj12Banner = istj12Banner,
                        showEstp13Banner = estp13Banner,
                        showSummerCard = summerCard,
                        showEnfj14Banner = enfj14Banner,
                        showAllMbtiBanner = allMbtiBanner,
                    )
                }.collect { state ->
                    _uiState.value = state
                }
            } catch (e: Exception) {
                _uiState.value = HomeUiState.Error(e.message ?: "알 수 없는 오류가 발생했습니다")
            }
        }
    }

    private fun showNewYearCard(): Boolean {
        return LocalDate.now().let { it.year == 2027 && it.monthValue == 1 && it.dayOfMonth <= 10 }
    }

    // 화이트데이 특집 배너: 3월 13~14일에만 노출 (25차 스프린트)
    private fun showWhiteDayBanner(): Boolean {
        return LocalDate.now().let { it.monthValue == 3 && it.dayOfMonth in 13..14 }
    }

    // 가정의 달 감사 카드: 4월 24일~5월 8일에만 노출 (26차 스프린트)
    private fun showGratitudeCardBanner(): Boolean {
        return LocalDate.now().let { date ->
            (date.monthValue == 4 && date.dayOfMonth >= 24) ||
                    (date.monthValue == 5 && date.dayOfMonth <= 8)
        }
    }

    // 가정의 달 사전 홍보 배너: 2027년 4월 10일~23일에만 노출 (28차 스프린트)
    private fun showGratitudeTeaserBanner(): Boolean {
        return LocalDate.now().let {
            it.year == 2027 && it.monthValue == 4 && it.dayOfMonth in 10..23
        }
    }

    private fun loadTrendingPosts() {
        viewModelScope.launch {
            runCatching {
                val posts = chatApi.getTrendingPosts(limit = 3)
                _trendingPosts.value = posts
            }.onFailure { e ->
                android.util.Log.w("HomeViewModel", "Failed to load trending posts", e)
            }
        }
    }

    private suspend fun showOpenBetaBanner(): Boolean {
        val dismissed = prefs.isOpenBetaBannerDismissed.first()
        return !dismissed
    }

    private suspend fun showDau10kBanner(): Boolean {
        val dismissed = prefs.isDau10kBannerDismissed.first()
        return !dismissed
    }

    private suspend fun showLora8Banner(): Boolean {
        val shown = prefs.isLora8BannerShown.first()
        return !shown
    }

    private suspend fun showLora9Banner(): Boolean {
        val shown = prefs.isLora9BannerShown.first()
        return !shown
    }

    // ── 31차: 어린이날 시즌 카드 ─────────────────────────────────────────────
    private fun showChildrenDayCard(): Boolean {
        return LocalDate.now().let { it.year == 2027 && it.monthValue == 5 && it.dayOfMonth in 1..5 }
    }

    // ── 33차: ESFP 10종 완성 배너 ────────────────────────────────────────────
    private suspend fun showEsfp10Banner(): Boolean {
        val shown = prefs.isLora10BannerShown.first()
        return !shown
    }

    fun dismissEsfp10Banner() {
        viewModelScope.launch {
            prefs.setLora10BannerShown(true)
            _uiState.update { state ->
                if (state is HomeUiState.Success) state.copy(showEsfp10Banner = false) else state
            }
        }
    }

    // ── 34차: ENTJ 11종 완성 배너 ────────────────────────────────────────────
    private suspend fun showEntj11Banner(): Boolean {
        val shown = prefs.isLora11BannerShown.first()
        return !shown
    }

    fun dismissEntj11Banner() {
        viewModelScope.launch {
            prefs.setLora11BannerShown(true)
            _uiState.update { state ->
                if (state is HomeUiState.Success) state.copy(showEntj11Banner = false) else state
            }
        }
    }

    // ── 34차: ISTJ 12종 완성 배너 ────────────────────────────────────────────
    private suspend fun showIstj12Banner(): Boolean {
        val shown = prefs.isLora12BannerShown.first()
        return !shown
    }

    fun dismissIstj12Banner() {
        viewModelScope.launch {
            prefs.setLora12BannerShown(true)
            _uiState.update { state ->
                if (state is HomeUiState.Success) state.copy(showIstj12Banner = false) else state
            }
        }
    }

    // ── 34차: 여름 바이럴 카드 섹션 (6~8월) ──────────────────────────────────
    private fun showSummerCard(): Boolean {
        return LocalDate.now().monthValue in 6..8
    }

    // ── 35차: ESTP 13종 완성 배너 ────────────────────────────────────────────
    private suspend fun showEstp13Banner(): Boolean {
        val shown = prefs.isLora13BannerShown.first()
        return !shown
    }

    fun dismissEstp13Banner() {
        viewModelScope.launch {
            prefs.setLora13BannerShown(true)
            _uiState.update { state ->
                if (state is HomeUiState.Success) state.copy(showEstp13Banner = false) else state
            }
        }
    }

    // ── 36차: ENFJ 14종 완성 배너 ────────────────────────────────────────────
    private suspend fun showEnfj14Banner(): Boolean {
        val shown = prefs.isLora14BannerShown.first()
        return !shown
    }

    fun dismissEnfj14Banner() {
        viewModelScope.launch {
            prefs.setLora14BannerShown(true)
            _uiState.update { state ->
                if (state is HomeUiState.Success) state.copy(showEnfj14Banner = false) else state
            }
        }
    }

    // ── 37차: 16종 전체 완성 배너 ────────────────────────────────────────────
    private suspend fun showAllMbtiBanner(): Boolean {
        val shown = prefs.isAllMbtiBannerShown.first()
        return !shown
    }

    fun dismissAllMbtiBanner() {
        viewModelScope.launch {
            prefs.setAllMbtiBannerShown(true)
            _uiState.update { state ->
                if (state is HomeUiState.Success) state.copy(showAllMbtiBanner = false) else state
            }
        }
    }

    fun dismissOpenBetaBanner() {
        viewModelScope.launch {
            prefs.setOpenBetaBannerDismissed(true)
            _uiState.update { state ->
                if (state is HomeUiState.Success) state.copy(openBetaBanner = false) else state
            }
        }
    }

    fun dismissDau10kBanner() {
        viewModelScope.launch {
            prefs.setDau10kBannerDismissed(true)
            _uiState.update { state ->
                if (state is HomeUiState.Success) state.copy(dau10kBanner = false) else state
            }
        }
    }

    fun dismissLora8Banner() {
        viewModelScope.launch {
            prefs.setLora8BannerShown(true)
            _uiState.update { state ->
                if (state is HomeUiState.Success) state.copy(showLora8Banner = false) else state
            }
        }
    }

    fun dismissLora9Banner() {
        viewModelScope.launch {
            prefs.setLora9BannerShown(true)
            _uiState.update { state ->
                if (state is HomeUiState.Success) state.copy(showLora9Banner = false) else state
            }
        }
    }

    fun loadEventTrendingPosts() {
        viewModelScope.launch {
            try {
                val posts = chatApi.getEventTrendingPosts()
                _eventTrendingPosts.value = posts.map { it.toUi() }
            } catch (e: Exception) {
                // 조용히 실패 (이벤트 섹션은 부가 기능)
            }
        }
    }

    init {
        // 캐릭터가 없으면 프리셋 자동 생성
        viewModelScope.launch {
            characterRepo.seedPresetsIfEmpty()
        }

        viewModelScope.launch {
            characters.collect { _ ->
                val lastMsgs = messageDao.getLastMessagePerCharacter()
                val map = lastMsgs.associate { msg ->
                    msg.characterId to LastMessageInfo(
                        text = msg.text,
                        timestamp = msg.createdAt,
                        isFromUser = msg.isFromUser
                    )
                }
                _lastMessages.value = map
            }
        }

        syncHomeUiState()
        loadTrendingPosts()
        loadEventTrendingPosts()
    }

    fun createCharacter(
        name: String,
        mbti: String,
        speechStyle: String,
        relationship: String,
        avatarId: String,
        revisedPrompt: String? = null,
        onCreated: (Long) -> Unit
    ) {
        viewModelScope.launch {
            val id = characterRepo.create(name, mbti, speechStyle, relationship, avatarId)

            // img: 캐릭터이고 revisedPrompt가 있으면 표정 세트 백그라운드 생성 시작
            if (avatarId.startsWith("img:") && revisedPrompt != null) {
                launch {
                    try {
                        val response = chatApi.generateImageSet(
                            ImageSetRequest(
                                basePrompt = revisedPrompt,
                                characterId = id.toString()
                            )
                        )
                        // taskId를 SharedPreferences에 저장하여 ChatViewModel에서 폴링
                        prefs.setExpressionSetTaskId(id, response.taskId)
                    } catch (e: Exception) {
                        android.util.Log.w("HomeViewModel", "Expression set generation start failed", e)
                    }
                }
            }

            onCreated(id)
        }
    }

    fun deleteCharacter(id: Long) {
        viewModelScope.launch {
            characterRepo.delete(id)
        }
    }
}
