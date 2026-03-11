package com.example.mbtichatfriend.ui.letter

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.example.mbtichatfriend.data.repository.LetterRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class LetterState(
    val isLoading: Boolean = false,
    val hasLetter: Boolean = false,
    val characterName: String = "",
    val content: String = "",
    val generatedDate: String = "",
    val error: String? = null,
)

@HiltViewModel
class LetterViewModel @Inject constructor(
    private val letterRepository: LetterRepository,
) : ViewModel() {

    private val _state = MutableStateFlow(LetterState())
    val state: StateFlow<LetterState> = _state

    fun checkForLetter(roomId: String, characterId: String, characterName: String) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true)
            letterRepository.getLatestLetter(roomId, characterId)
                .onSuccess { response ->
                    _state.value = LetterState(
                        isLoading = false,
                        hasLetter = response.has_letter,
                        characterName = characterName,
                        content = response.content,
                        generatedDate = response.generated_date,
                    )
                }
                .onFailure {
                    _state.value = _state.value.copy(isLoading = false, error = it.message)
                }
        }
    }
}
