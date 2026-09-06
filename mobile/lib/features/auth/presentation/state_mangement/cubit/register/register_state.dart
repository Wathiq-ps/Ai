enum RegisterStatus { initial, success, error }

class RegisterState {
  final String emailOrPhone;
  final String? errorMessage;
  final RegisterStatus status;
  final bool isLoading;

  const RegisterState({
    this.emailOrPhone = '',
    this.errorMessage,
    this.status = RegisterStatus.initial,
    this.isLoading = false,
  });

  RegisterState copyWith({
    String? emailOrPhone,
    String? errorMessage,
    RegisterStatus? status,
    bool? isLoading,
  }) {
    return RegisterState(
      emailOrPhone: emailOrPhone ?? this.emailOrPhone,
      errorMessage: errorMessage,
      status: status ?? this.status,
      isLoading: isLoading ?? this.isLoading,
    );
  }
}