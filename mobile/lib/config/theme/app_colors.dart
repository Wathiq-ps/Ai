import 'package:flutter/material.dart';

class AppColors {
  AppColors._();

  // ─────────────────────────────────────────────
  // Brand Colors
  // ─────────────────────────────────────────────

  /// Primary brand color
  static const Color primary = Color(0xFF00113A);

  /// Secondary brand color
  static const Color secondary = Color(0xFFB5C4FF);

  /// Accent / CTA color
  static const Color accent = Color(0xFFFABD00);

  // ─────────────────────────────────────────────
  // Basic Colors
  // ─────────────────────────────────────────────

  static const Color white = Color(0xFFFFFFFF);

  static const Color black = Color(0xFF000000);

  // ─────────────────────────────────────────────
  // Semantic Colors
  // ─────────────────────────────────────────────

  /// Used for validation errors, error text,
  /// borders and error states.
  static const Color error = Color(0xFFBE1510);

  /// Used for successful actions and states.
  static const Color success = Color(0xFF2E7D32);

  // ─────────────────────────────────────────────
  // Optional Supporting Colors
  // ─────────────────────────────────────────────

  static const Color transparent = Colors.transparent;

  static const Color background = Color(0xFFF8F9FC);

  static const Color surface = Color(0xFFFFFFFF);

  static const Color border = Color(0xFFD9DDE7);

  static const Color textPrimary = Color(0xFF00113A);

  static const Color textSecondary = Color(0xFF667085);

  static const Color disabled = Color(0xFFBFC3CC);

  // ─────────────────────────────────────────────
  // Property Colors
  // ─────────────────────────────────────────────

  static const Color primaryDark = Color(0xFF00113A);

  static const Color overlayDark =
      Color.fromRGBO(0, 35, 102, 0.95);

  static const Color overlayMedium =
      Color.fromRGBO(0, 0, 0, 0.60);

  static const Color overlayLight =
      Color.fromRGBO(0, 0, 0, 0.20);

  static const Color white70 =
      Color.fromRGBO(255, 255, 255, 0.7);

  static const Color white60 =
      Color.fromRGBO(255, 255, 255, 0.6);

  static const Color white40 =
      Color.fromRGBO(255, 255, 255, 0.4);

  static const Color shadowColor =
      Color.fromRGBO(0, 0, 0, 0.25);

  static const Color cardSelectedBg =
      Color.fromRGBO(255, 255, 255, 0.10);

  static const Color cardUnselectedBg =
      Color.fromRGBO(255, 255, 255, 0.05);

  static const Color cardBorder =
      Color.fromRGBO(255, 255, 255, 0.10);

  static const Color errorColor = Color(0xFFBE1510);

  // ─────────────────────────────────────────────
  // Auth / Gradient
  // ─────────────────────────────────────────────

  static const Color backgroundGradient = Color(0xFF002366);

  // ─────────────────────────────────────────────
  // Top Snack Bar
  // ─────────────────────────────────────────────

  static const Color topSnackBarTitle = Color(0xFF001947);

  static const Color topSnackBarMessage =
      Color.fromRGBO(0, 17, 58, 0.95);

  static const Color topSnackBarBorder =
      Color.fromRGBO(195, 198, 214, 0.2);

  static const Color topSnackBarShadow =
      Color.fromRGBO(0, 85, 204, 0.12);

  static const Color topSnackBarIconOverlay =
      Color.fromRGBO(0, 109, 67, 0.1);

  // ─────────────────────────────────────────────
  // Property / Photo Cards
  // ─────────────────────────────────────────────

  static const Color iconBg =
      Color.fromRGBO(226, 226, 229, 0.2);

  static const Color card2SelectedBg =
      Color.fromRGBO(0, 63, 156, 0.2);

  static const Color card2UnselectedBg =
      Color.fromRGBO(195, 198, 214, 0.3);

  static const Color photoBorder =
      Color.fromRGBO(177, 197, 255, 0.4);

  static const Color addPhotoBg =
      Color.fromRGBO(249, 249, 252, 0.05);
}