package com.example.mbtichatfriend.navigation

import androidx.compose.animation.AnimatedContentTransitionScope
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.example.mbtichatfriend.ui.character.CharacterProfileScreen
import com.example.mbtichatfriend.ui.chat.ChatScreen
import com.example.mbtichatfriend.ui.gallery.GalleryScreen
import com.example.mbtichatfriend.ui.home.CreateCharacterSheet
import com.example.mbtichatfriend.ui.home.HomeScreen
import com.example.mbtichatfriend.ui.home.HomeViewModel
import com.example.mbtichatfriend.ui.login.LoginScreen
import com.example.mbtichatfriend.ui.onboarding.AgeScreen
import com.example.mbtichatfriend.ui.onboarding.GenderScreen
import com.example.mbtichatfriend.ui.onboarding.MbtiSelectScreen
import com.example.mbtichatfriend.ui.onboarding.NicknameScreen
import com.example.mbtichatfriend.ui.onboarding.OnboardingViewModel
import com.example.mbtichatfriend.ui.onboarding.StyleSelectScreen
import com.example.mbtichatfriend.ui.settings.SettingsScreen
import com.example.mbtichatfriend.ui.splash.SplashScreen
import com.example.mbtichatfriend.ui.diary.DiaryScreen
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
            NicknameScreen(
                viewModel = onboardingViewModel,
                onNext = { navController.navigate(Route.Gender.route) }
            )
        }

        composable(Route.Gender.route) {
            GenderScreen(
                viewModel = onboardingViewModel,
                onNext = { navController.navigate(Route.Age.route) },
                onBack = { navController.popBackStack() }
            )
        }

        composable(Route.Age.route) {
            AgeScreen(
                viewModel = onboardingViewModel,
                onNext = { navController.navigate(Route.MbtiSelect.route) },
                onBack = { navController.popBackStack() }
            )
        }

        composable(Route.MbtiSelect.route) {
            MbtiSelectScreen(
                viewModel = onboardingViewModel,
                onNext = { navController.navigate(Route.StyleSelect.route) },
                onBack = { navController.popBackStack() }
            )
        }

        composable(Route.StyleSelect.route) {
            StyleSelectScreen(
                viewModel = onboardingViewModel,
                onComplete = {
                    navController.navigate(Route.Home.route) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onBack = { navController.popBackStack() }
            )
        }

        // === 홈 (캐릭터 리스트) ===
        composable(Route.Home.route) {
            val homeViewModel: HomeViewModel = hiltViewModel()
            var showCreateSheet by remember { mutableStateOf(false) }

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
                viewModel = homeViewModel
            )

            if (showCreateSheet) {
                ModalBottomSheet(
                    onDismissRequest = { showCreateSheet = false },
                    sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
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
            ChatScreen(
                onBack = { navController.popBackStack() },
                onProfile = { characterId ->
                    navController.navigate(Route.CharacterProfile.createRoute(characterId))
                },
                onVoiceCall = { characterId ->
                    navController.navigate(Route.VoiceCall.createRoute(characterId))
                }
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

        // === 설정 ===
        composable(Route.Settings.route) {
            SettingsScreen(
                onBack = { navController.popBackStack() },
                onLogout = {
                    navController.navigate(Route.Login.route) {
                        popUpTo(0) { inclusive = true }
                    }
                }
            )
        }
    }
}
