package com.example.mbtichatfriend.navigation

sealed class Route(val route: String) {
    data object Splash : Route("splash")
    data object Login : Route("login")
    data object Nickname : Route("onboarding/nickname")
    data object Gender : Route("onboarding/gender")
    data object Age : Route("onboarding/age")
    data object MbtiSelect : Route("onboarding/mbti")
    data object StyleSelect : Route("onboarding/style")
    data object Home : Route("home")
    data object Chat : Route("chat/{characterId}") {
        fun createRoute(characterId: Long) = "chat/$characterId"
    }
    data object CharacterProfile : Route("character/{characterId}") {
        fun createRoute(characterId: Long) = "character/$characterId"
    }
    data object Settings : Route("settings")
    data object VoiceCall : Route("voicecall/{characterId}") {
        fun createRoute(characterId: Long) = "voicecall/$characterId"
    }
    data object Diary : Route("diary/{characterId}") {
        fun createRoute(characterId: Long) = "diary/$characterId"
    }
    data object Gallery : Route("gallery")
}
