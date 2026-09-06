import 'package:flutter_bloc/flutter_bloc.dart';
import 'package:mobile/features/auth/presentation/state_mangement/cubit/register/register_state.dart';
import '../../../../../../core/utils/validators.dart';

class RegisterCubit extends Cubit<RegisterState> {
  RegisterCubit() : super(const RegisterState());

  void emailChange(String emailValue) {
    emit(state.copyWith(
      emailOrPhone: emailValue,
      errorMessage: null,
      status: RegisterStatus.initial,
    ));
  }

  void emailValidate() {
    final error = state.emailOrPhone.validateEmail();

    if (error == null) {
      emit(state.copyWith(
        errorMessage: null,
        status: RegisterStatus.success,
      ));
    } else {
      emit(state.copyWith(
        errorMessage: error,
        status: RegisterStatus.error,
      ));
    }
  }
}