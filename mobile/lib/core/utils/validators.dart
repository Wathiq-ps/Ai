import 'package:flutter/widgets.dart';
import 'package:mobile/core/constant/strings.dart';


class _ValidatorPatterns {
  _ValidatorPatterns._();

  static final RegExp email = RegExp(r'^[\w.-]+@[\w.-]+\.\w{2,}$');
}


extension StringValidators on String? {
  bool get _isBlank => this == null || this!.trim().isEmpty;

  String? validateRequired(BuildContext context) {
    if (_isBlank) return AppStrings.textFieldErrorEmpty;
    return null;
  }

  String? validateName(BuildContext context) => validateRequired(context);

  String? validatePhone(BuildContext context) => validateRequired(context);


  String? validateEmail() {
    if (_isBlank) return AppStrings.emailIsRequired;
    if (!_ValidatorPatterns.email.hasMatch(this!.trim())) {
      return AppStrings.textFieldWrongEmail;
    }
    return null;
  }



}