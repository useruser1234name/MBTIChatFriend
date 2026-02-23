package com.example.mbtichatfriend.model

enum class Gender {
    MALE, FEMALE, OTHER
}

enum class AgeGroup(val label: String) {
    TEEN("10대"),
    TWENTIES("20대"),
    THIRTIES("30대"),
    FORTIES_PLUS("40대 이상")
}

enum class MbtiType(val description: String) {
    INTJ("전략가 - 상상력이 풍부한 전략가"),
    INTP("논리술사 - 끝없는 지식 탐구자"),
    ENTJ("통솔자 - 대담한 리더"),
    ENTP("변론가 - 똑똑한 호기심쟁이"),
    INFJ("옹호자 - 조용하고 신비로운 이상주의자"),
    INFP("중재자 - 항상 선한 마음을 가진 몽상가"),
    ENFJ("선도자 - 카리스마 넘치는 리더"),
    ENFP("활동가 - 자유로운 영혼의 사교적인 사람"),
    ISTJ("현실주의자 - 사실을 중시하는 신뢰할 수 있는 사람"),
    ISFJ("수호자 - 헌신적이고 따뜻한 수호자"),
    ESTJ("경영자 - 뛰어난 관리자"),
    ESFJ("집정관 - 배려심 많은 사교적인 사람"),
    ISTP("장인 - 대담하고 실용적인 실험가"),
    ISFP("모험가 - 유연하고 매력적인 예술가"),
    ESTP("사업가 - 에너지 넘치는 모험가"),
    ESFP("연예인 - 자발적이고 에너지 넘치는 연예인")
}

enum class SpeechStyle(val label: String) {
    FORMAL("존댓말"),
    CASUAL("반말"),
    TSUNDERE("츤데레"),
    SWEET("다정")
}

enum class Relationship(val label: String) {
    FRIEND("친구"),
    LOVER("연인"),
    SENIOR_JUNIOR("선후배")
}

data class UserProfile(
    val nickname: String = "",
    val gender: Gender = Gender.MALE,
    val ageGroup: AgeGroup = AgeGroup.TWENTIES,
    val partnerMbti: MbtiType = MbtiType.ENFP,
    val speechStyle: SpeechStyle = SpeechStyle.CASUAL,
    val relationship: Relationship = Relationship.FRIEND
)
