package com.example.mbtichatfriend.navigation

import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.example.mbtichatfriend.ui.character.CharacterProfileScreen
import com.example.mbtichatfriend.ui.chat.ChatScreen
import com.example.mbtichatfriend.ui.community.CommunityScreen
import com.example.mbtichatfriend.ui.compatibility.CompatibilityScreen
import com.example.mbtichatfriend.ui.profile.NotificationScreen
import com.example.mbtichatfriend.ui.profile.YearReportScreen
import com.example.mbtichatfriend.ui.community.PostDetailScreen
import com.example.mbtichatfriend.ui.community.WritePostScreen
import com.example.mbtichatfriend.ui.gallery.GalleryScreen
import com.example.mbtichatfriend.ui.home.CreateCharacterSheet
import com.example.mbtichatfriend.ui.home.HomeScreen
import com.example.mbtichatfriend.ui.home.HomeViewModel
import com.example.mbtichatfriend.ui.login.LoginScreen
import com.example.mbtichatfriend.model.PRESET_CHARACTERS
import com.example.mbtichatfriend.ui.onboarding.AgeScreen
import com.example.mbtichatfriend.ui.onboarding.GenderScreen
import com.example.mbtichatfriend.ui.onboarding.MbtiSelectScreen
import com.example.mbtichatfriend.ui.onboarding.NicknameScreen
import com.example.mbtichatfriend.ui.onboarding.OnboardingScreen
import com.example.mbtichatfriend.ui.onboarding.OnboardingViewModel
import com.example.mbtichatfriend.ui.onboarding.StarterSelectionScreen
import com.example.mbtichatfriend.ui.onboarding.StyleSelectScreen
import com.example.mbtichatfriend.ui.settings.SettingsScreen
import com.example.mbtichatfriend.ui.splash.SplashScreen
import com.example.mbtichatfriend.ui.chat.ChatViewModel
import com.example.mbtichatfriend.ui.diary.DiaryEntryScreen
import com.example.mbtichatfriend.ui.diary.DiaryScreen
import com.example.mbtichatfriend.ui.diary.DiaryWeeklyReportScreen
import com.example.mbtichatfriend.ui.premium.PremiumScreen
import com.example.mbtichatfriend.ui.settings.LanguageSettingScreen
import com.example.mbtichatfriend.ui.voicecall.VoiceCallScreen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AppNavHost(navController: NavHostController, modifier: Modifier = Modifier) {
    val onboardingViewModel: OnboardingViewModel = hiltViewModel()
    val isOnboardingDone by onboardingViewModel.isOnboardingCompleted.collectAsState(initial = false)

    NavHost(
        navController = navController,
        startDestination = Route.Splash.route,
        modifier = modifier,
        enterTransition = {
            slideIntoContainer(AnimatedContentTransitionScope.SlideDirection.Start, tween(300))
        },
        exitTransition = {
            slideOutOfContainer(AnimatedContentTransitionScope.SlideDirection.Start, tween(300))
        },
        popEnterTransition = {
            slideIntoContainer(AnimatedContentTransitionScope.SlideDirection.End, tween(300))
        },
        popExitTransition = {
            slideOutOfContainer(AnimatedContentTransitionScope.SlideDirection.End, tween(300))
        }
    ) {
        // === 스플래시 ===
        composable(
            Route.Splash.route,
            enterTransition = { fadeIn(tween(300)) },
            exitTransition = { fadeOut(tween(300)) }
        ) {
            SplashScreen(
                onFinished = {
                    val dest = if (isOnboardingDone) Route.Home.route else Route.Login.route
                    navController.navigate(dest) {
                        popUpTo(Route.Splash.route) { inclusive = true }
                    }
                }
            )
        }

        // === 로그인 ===
        composable(Route.Login.route) {
            LoginScreen(
                onSignInComplete = {
                    navController.navigate(Route.Nickname.route) {
                        popUpTo(Route.Login.route) { inclusive = true }
                    }
                }
            )
        }

        // === 온보딩 ===
        composable(Route.Nickname.route) {
            // onboarding_step: step_index=0 (Nickname)
            LaunchedEffect(Unit) { onboardingViewModel.trackStep(0) }
            NicknameScreen(
                viewModel = onboardingViewModel,
                onNext = { navController.navigate(Route.Gender.route) }
            )
        }

        composable(Route.Gender.route) {
            // onboarding_step: step_index=1 (Gender)
            LaunchedEffect(Unit) { onboardingViewModel.trackStep(1) }
            GenderScreen(
                viewModel = onboardingViewModel,
                onNext = { navController.navigate(Route.Age.route) },
                onBack = { navController.popBackStack() }
            )
        }

        composable(Route.Age.route) {
            // onboarding_step: step_index=2 (Age)
            LaunchedEffect(Unit) { onboardingViewModel.trackStep(2) }
            AgeScreen(
                viewModel = onboardingViewModel,
                onNext = { navController.navigate(Route.MbtiSelect.route) },
                onBack = { navController.popBackStack() }
            )
        }

        composable(Route.MbtiSelect.route) {
            // onboarding_step: step_index=3 (MbtiSelect)
            LaunchedEffect(Unit) { onboardingViewModel.trackStep(3) }
            MbtiSelectScreen(
                viewModel = onboardingViewModel,
                onNext = { navController.navigate(Route.StyleSelect.route) },
                onBack = { navController.popBackStack() }
            )
        }

        composable(Route.StyleSelect.route) {
            // onboarding_step: step_index=4 (StyleSelect / 캐릭터 선택)
            LaunchedEffect(Unit) { onboardingViewModel.trackStep(4) }
            // MBTI 선택 + 캐릭터 추천을 인라인으로 통합한 OnboardingScreen.
            // 기존 4단계(별도 캐릭터 추천 화면)를 3단계로 통합: MBTI 선택 완료 시 하단에 슬라이드인.
            OnboardingScreen(
                onMbtiSelected = { mbti ->
                    runCatching { com.example.mbtichatfriend.model.MbtiType.valueOf(mbti) }
                        .getOrNull()
                        ?.let { onboardingViewModel.updatePartnerMbti(it) }
                },
                onSkipToTest = { /* 외부 MBTI 테스트 링크 — 추후 구현 */ },
                onCharacterSelected = { character ->
                    onboardingViewModel.updateSelectedCharacter(character)
                    // 캐릭터 선택 완료 이벤트 — character_id(=mbti)를 payload에 포함
                    onboardingViewModel.trackCharacterSelected(character)
                    navController.navigate(Route.StarterSelection.route)
                },
            )
        }

        composable(Route.StarterSelection.route) {
            val selectedCharacter = onboardingViewModel.selectedCharacter
            val characterName = selectedCharacter?.name
                ?: PRESET_CHARACTERS.firstOrNull { it.mbti == onboardingViewModel.partnerMbti.name }?.name
                ?: "친구"
            StarterSelectionScreen(
                characterName = characterName,
                starters = emptyList(),
                isLoading = false,
                onStarterConfirmed = { _ ->
                    onboardingViewModel.saveOnboarding {
                        navController.navigate(Route.Home.route) {
                            popUpTo(0) { inclusive = true }
                        }
                    }
                },
                viewModel = onboardingViewModel,
            )
        }

        // === 홈 (캐릭터 리스트) ===
        composable(Route.Home.route) {
            val homeViewModel: HomeViewModel = hiltViewModel()
            var showCreateSheet by remember { mutableStateOf(false) }
            val homeUserMbti by homeViewModel.userMbti.collectAsState()

            HomeScreen(
                onCharacterClick = { characterId ->
                    navController.navigate(Route.Chat.createRoute(characterId))
                },
                onCreateCharacter = { showCreateSheet = true },
                onSettings = {
                    navController.navigate(Route.Settings.route)
                },
                onGallery = {
                    navController.navigate(Route.Gallery.route)
                },
                onCommunityPostClick = { postId ->
                    navController.navigate(Route.PostDetail.createRoute(postId))
                },
                onCompatibility = {
                    val myMbti = homeUserMbti.ifEmpty { "INFP" }
                    navController.navigate(Route.Compatibility.createRoute(myMbti, "ENFP"))
                },
                viewModel = homeViewModel
            )

            if (showCreateSheet) {
                ModalBottomSheet(
                    onDismissRequest = { showCreateSheet = false },
                    sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true),
                    // U1: MaterialTheme.shapes.extraLarge가 AppShapes 배선으로 28dp→24dp 바뀌므로
                    // 바텀시트 상단 코너(현상) 유지를 위해 기존 M3 기본값(extraLarge=28dp)을 명시적으로 고정.
                    shape = RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp)
                ) {
                    CreateCharacterSheet(
                        onDismiss = { showCreateSheet = false },
                        onCreate = { name, mbti, speechStyle, relationship, avatarId ->
                            homeViewModel.createCharacter(name, mbti, speechStyle, relationship, avatarId) { characterId ->
                                showCreateSheet = false
                                navController.navigate(Route.Chat.createRoute(characterId))
                            }
                        }
                    )
                }
            }
        }

        // === 채팅 ===
        composable(
            route = Route.Chat.route,
            arguments = listOf(navArgument("characterId") { type = NavType.StringType })
        ) {
            val chatViewModel: ChatViewModel = hiltViewModel()
            val chatUiState by chatViewModel.uiState.collectAsState()
            val characterMbti = (chatUiState as? com.example.mbtichatfriend.ui.chat.ChatUiState.Success)
                ?.character?.mbti ?: ""
            val myMbti by chatViewModel.myMbti.collectAsState()
            ChatScreen(
                onBack = { navController.popBackStack() },
                onProfile = { characterId ->
                    navController.navigate(Route.CharacterProfile.createRoute(characterId))
                },
                onVoiceCall = { characterId ->
                    navController.navigate(Route.VoiceCall.createRoute(characterId))
                },
                onNavigateToCompatibility = {
                    if (myMbti.isNotEmpty() && characterMbti.isNotEmpty()) {
                        navController.navigate(Route.Compatibility.createRoute(myMbti, characterMbti))
                    }
                },
                viewModel = chatViewModel,
            )
        }

        // === 캐릭터 프로필 ===
        composable(
            route = Route.CharacterProfile.route,
            arguments = listOf(navArgument("characterId") { type = NavType.StringType })
        ) { backStackEntry ->
            val characterId = backStackEntry.arguments?.getString("characterId")?.toLongOrNull() ?: 0L
            CharacterProfileScreen(
                characterId = characterId,
                onBack = { navController.popBackStack() },
                onChat = { id ->
                    navController.navigate(Route.Chat.createRoute(id)) {
                        popUpTo(Route.Home.route)
                    }
                },
                onVoiceCall = { id ->
                    navController.navigate(Route.VoiceCall.createRoute(id))
                },
                onDiary = { id ->
                    navController.navigate(Route.Diary.createRoute(id))
                },
                onDeleted = {
                    navController.navigate(Route.Home.route) {
                        popUpTo(Route.Home.route) { inclusive = true }
                    }
                }
            )
        }

        // === 일기장 ===
        composable(
            route = Route.Diary.route,
            arguments = listOf(navArgument("characterId") { type = NavType.StringType }),
            enterTransition = { fadeIn(tween(300)) },
            exitTransition = { fadeOut(tween(300)) },
            popEnterTransition = { fadeIn(tween(300)) },
            popExitTransition = { fadeOut(tween(300)) }
        ) {
            DiaryScreen(onBack = { navController.popBackStack() })
        }

        // === 음성 대화 ===
        composable(
            route = Route.VoiceCall.route,
            arguments = listOf(navArgument("characterId") { type = NavType.StringType }),
            enterTransition = { fadeIn(tween(400)) },
            exitTransition = { fadeOut(tween(400)) },
            popEnterTransition = { fadeIn(tween(400)) },
            popExitTransition = { fadeOut(tween(400)) }
        ) {
            VoiceCallScreen(
                onBack = { navController.popBackStack() }
            )
        }

        // === 캐릭터 갤러리 ===
        composable(
            route = Route.Gallery.route,
            enterTransition = { slideIntoContainer(AnimatedContentTransitionScope.SlideDirection.Start, tween(300)) },
            exitTransition = { slideOutOfContainer(AnimatedContentTransitionScope.SlideDirection.Start, tween(300)) },
            popEnterTransition = { slideIntoContainer(AnimatedContentTransitionScope.SlideDirection.End, tween(300)) },
            popExitTransition = { slideOutOfContainer(AnimatedContentTransitionScope.SlideDirection.End, tween(300)) }
        ) {
            GalleryScreen(
                onBack = { navController.popBackStack() },
                onCharacterAdded = { characterId ->
                    navController.navigate(Route.Chat.createRoute(characterId)) {
                        popUpTo(Route.Home.route)
                    }
                }
            )
        }

        // === 커뮤니티 ===
        composable(Route.Community.route) {
            CommunityScreen(
                onNavigateToWrite = { navController.navigate(Route.WritePost.route) },
                onNavigateToDetail = { postId -> navController.navigate(Route.PostDetail.createRoute(postId)) },
            )
        }

        // === 고민 쓰기 ===
        composable(Route.WritePost.route) {
            WritePostScreen(
                onNavigateBack = { navController.popBackStack() },
            )
        }

        // === 게시글 상세 ===
        composable(
            route = Route.PostDetail.route,
            arguments = listOf(navArgument("postId") { type = NavType.LongType }),
        ) { backStackEntry ->
            val postId = backStackEntry.arguments?.getLong("postId") ?: 0L
            PostDetailScreen(
                postId = postId,
                onNavigateBack = { navController.popBackStack() },
            )
        }

        // === 설정 ===
        composable(Route.Settings.route) {
            SettingsScreen(
                onBack = { navController.popBackStack() },
                onLogout = {
                    navController.navigate(Route.Login.route) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onYearReport = {
                    navController.navigate(Route.YearReport.route)
                },
                onLanguageSetting = {
                    navController.navigate(Route.LanguageSetting.route)
                },
            )
        }

        // === 궁합 (21차 스프린트) ===
        composable(
            route = Route.Compatibility.route,
            arguments = listOf(
                navArgument("myMbti") { type = NavType.StringType },
                navArgument("characterMbti") { type = NavType.StringType },
            ),
            enterTransition = { fadeIn(tween(300)) },
            exitTransition = { fadeOut(tween(300)) },
            popEnterTransition = { fadeIn(tween(300)) },
            popExitTransition = { fadeOut(tween(300)) },
        ) { backStackEntry ->
            val myMbti = backStackEntry.arguments?.getString("myMbti") ?: ""
            val characterMbti = backStackEntry.arguments?.getString("characterMbti") ?: ""
            CompatibilityScreen(
                myMbti = myMbti,
                characterMbti = characterMbti,
                onNavigateBack = { navController.popBackStack() },
            )
        }

        // === 알림 (21차 스프린트) ===
        composable(
            route = Route.Notifications.route,
            enterTransition = { fadeIn(tween(300)) },
            exitTransition = { fadeOut(tween(300)) },
            popEnterTransition = { fadeIn(tween(300)) },
            popExitTransition = { fadeOut(tween(300)) },
        ) {
            NotificationScreen(
                onNavigateBack = { navController.popBackStack() },
                onNavigateToCommunityPost = { postId ->
                    navController.navigate(Route.PostDetail.createRoute(postId))
                },
                onNavigateToReferral = {
                    navController.navigate(Route.Settings.route)
                },
            )
        }

        // === 연말 대화 리포트 (22차 스프린트) ===
        composable(
            route = Route.YearReport.route,
            enterTransition = { fadeIn(tween(300)) },
            exitTransition = { fadeOut(tween(300)) },
            popEnterTransition = { fadeIn(tween(300)) },
            popExitTransition = { fadeOut(tween(300)) },
        ) {
            YearReportScreen(
                onNavigateBack = { navController.popBackStack() },
            )
        }

        // === 사용자 직접 입력 다이어리 (32차 스프린트) ===
        composable(
            route = Route.DiaryEntry.route,
            arguments = listOf(navArgument("characterId") { type = NavType.StringType }),
            enterTransition = { fadeIn(tween(300)) },
            exitTransition = { fadeOut(tween(300)) },
            popEnterTransition = { fadeIn(tween(300)) },
            popExitTransition = { fadeOut(tween(300)) },
        ) {
            DiaryEntryScreen(
                onBack = { navController.popBackStack() }
            )
        }

        // === 주간 감정 리포트 (32차 스프린트) ===
        composable(
            route = Route.DiaryWeeklyReport.route,
            enterTransition = { fadeIn(tween(300)) },
            exitTransition = { fadeOut(tween(300)) },
            popEnterTransition = { fadeIn(tween(300)) },
            popExitTransition = { fadeOut(tween(300)) },
        ) {
            DiaryWeeklyReportScreen(
                onBack = { navController.popBackStack() }
            )
        }

        // === 프리미엄 구독 (36차 스프린트) ===
        composable(
            route = Route.Premium.route,
            enterTransition = { fadeIn(tween(300)) },
            exitTransition = { fadeOut(tween(300)) },
            popEnterTransition = { fadeIn(tween(300)) },
            popExitTransition = { fadeOut(tween(300)) },
        ) {
            PremiumScreen(
                onBack = { navController.popBackStack() }
            )
        }

        // === 언어 설정 (36차 스프린트) ===
        composable(
            route = Route.LanguageSetting.route,
            enterTransition = { fadeIn(tween(300)) },
            exitTransition = { fadeOut(tween(300)) },
            popEnterTransition = { fadeIn(tween(300)) },
            popExitTransition = { fadeOut(tween(300)) },
        ) {
            LanguageSettingScreen(
                onBack = { navController.popBackStack() }
            )
        }
    }
}
