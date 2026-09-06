class AppErrorMapper {
  AppErrorMapper._();

  static const String genericError =
      'Something went wrong. Please try again';

  static String map(String backendMessage) {
    final msg = backendMessage.toLowerCase().trim();

    if (msg.isEmpty) {
      return genericError;
    }

    // ─────────────────────────────────────────
    // Authentication
    // ─────────────────────────────────────────

    if (msg.contains('invalid credentials') ||
        msg.contains('no active account')) {
      return 'Email or password is incorrect';
    }

    if (msg.contains('user not found')) {
      return 'No account found with this email';
    }

    if (msg.contains('email already exists')) {
      return 'This email is already registered';
    }

    // ─────────────────────────────────────────
    // OTP
    // ─────────────────────────────────────────

    if (msg.contains('invalid otp')) {
      return 'The code you entered is incorrect';
    }

    if (msg.contains('expired') && msg.contains('otp')) {
      return 'This code has expired. Please request a new one';
    }

    // ─────────────────────────────────────────
    // Network
    // ─────────────────────────────────────────

    if (msg.contains('network') ||
        msg.contains('timeout') ||
        msg.contains('socket') ||
        msg.contains('connection')) {
      return 'Check your internet connection and try again';
    }

    // ─────────────────────────────────────────
    // Account Status
    // ─────────────────────────────────────────

    if (msg.contains('blocked') ||
        msg.contains('suspended')) {
      return 'Your account has been suspended';
    }

    return genericError;
  }
}