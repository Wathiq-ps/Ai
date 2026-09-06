import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_svg/flutter_svg.dart';
import '../../config/theme/app_colors.dart';
import '../constant/app_icons.dart';
import '../extensions/media_query_extensions.dart';

class AppTopSnackBar extends StatelessWidget {
  const AppTopSnackBar({
    super.key,
    required this.title,
    required this.message,
    required this.prefixIcon,
    this.postfixIcon = AppIcons.cancel,
    this.onClose,
    this.width = 350,
    this.height = 75,
    this.gap = 10,
    this.titleMessageGap = 4,
    this.prefixIconWidth = 30,
    this.prefixIconHeight = 30,
    this.postfixIconWidth = 15,
    this.postfixIconHeight = 15,
    this.titleFontSize = 14,
    this.messageFontSize = 12,
  });

  final String title;
  final String message;
  final String prefixIcon;
  final String postfixIcon;
  final VoidCallback? onClose;
  final double width;
  final double height;
  final double gap;
  final double titleMessageGap;
  final double prefixIconWidth;
  final double prefixIconHeight;
  final double postfixIconWidth;
  final double postfixIconHeight;
  final double titleFontSize;
  final double messageFontSize;
  static const double _figmaWidth = 393;
  static const double _figmaHeight = 852;

  static void show(
      BuildContext context, {
        required String title,
        required String message,
        required String prefixIcon,
        String postfixIcon = AppIcons.cancel,
        VoidCallback? onClose,
        Duration duration = const Duration(seconds: 3),
        Duration fadeDuration = const Duration(milliseconds: 300),
      }) {
    final overlay = Overlay.of(context);

    final currentScreenWidth = context.screenWidth;
    final widthScale = currentScreenWidth / _figmaWidth;

    late OverlayEntry overlayEntry;

    overlayEntry = OverlayEntry(
      builder: (context) {
        return AppTopSnackBar(
          title: title,
          message: message,
          prefixIcon: prefixIcon,
          postfixIcon: postfixIcon,
          width: 350 * widthScale,
          height: 81 * widthScale,
          prefixIconWidth: 25 * widthScale,
          prefixIconHeight: 25 * widthScale,
          postfixIconWidth: 14 * widthScale,
          postfixIconHeight: 14 * widthScale,
          titleFontSize: 14 * widthScale,
          messageFontSize: 12 * widthScale,
          gap: 10 * widthScale,
          titleMessageGap: 10 * widthScale,
          onClose: () {
            if (overlayEntry.mounted) {
              overlayEntry.remove();
            }

            onClose?.call();
          },
        );
      },
    );

    overlay.insert(overlayEntry);

    Timer(duration, () {
      if (overlayEntry.mounted) {
        overlayEntry.remove();
      }
    });
  }

  double _getResponsiveScale(
      double currentScreenWidth,
      double currentScreenHeight,
      double heightScale,
      ) {
    final aspectRatio = currentScreenWidth / currentScreenHeight;

    if (aspectRatio >= 0.65) {
      // Tablets / Wider aspect ratios (Desktop / Landscape)
      return 0.85 * heightScale;
    } else if (aspectRatio >= 0.4) {
      // Standard phone aspect ratios
      return 1.0 * heightScale;
    } else {
      // Tall narrow screens
      return 1.15 * heightScale;
    }
  }

  double _getResponsiveGap(
      double currentScreenWidth,
      double currentScreenHeight,
      double heightScale,
      ) {
    final aspectRatio = currentScreenWidth / currentScreenHeight;

    if (aspectRatio >= 0.65) {
      return 5.0 * heightScale;
    } else {
      return 2.0 * heightScale;
    }
  }

  @override
  Widget build(BuildContext context) {
    final currentScreenWidth = context.screenWidth;
    final currentScreenHeight = context.screenHeight;
    final widthScale = currentScreenWidth / _figmaWidth;
    final heightScale = currentScreenHeight / _figmaHeight;

    final responsiveTextHeight = _getResponsiveScale(
      currentScreenWidth,
      currentScreenHeight,
      heightScale,
    );

    final responsiveGap = _getResponsiveGap(
      currentScreenWidth,
      currentScreenHeight,
      heightScale,
    );

    return SafeArea(
      child: Align(
        alignment: Alignment.topCenter,
        child: TweenAnimationBuilder<double>(
          tween: Tween(
            begin: 0.0,
            end: 1.0,
          ),
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeInOut,
          builder: (context, opacity, child) {
            return Opacity(
              opacity: opacity,
              child: child,
            );
          },
          child: ConstrainedBox(
            constraints: BoxConstraints(
              maxWidth: width,
            ),
            child: Container(
              width: double.infinity,
              height: height,
              padding: EdgeInsets.all(16 * widthScale),
              decoration: BoxDecoration(
                color: AppColors.surface,
                border: Border.all(
                  color: AppColors.topSnackBarBorder,
                ),
                borderRadius: BorderRadius.circular(9999),
                boxShadow: const [
                  BoxShadow(
                    offset: Offset(0, 10),
                    blurRadius: 30,
                    color: AppColors.topSnackBarShadow,
                  ),
                ],
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Container(
                    padding: EdgeInsets.all(6 * (prefixIconWidth / 30)),
                    decoration: const BoxDecoration(
                      color: AppColors.topSnackBarIconOverlay,
                      shape: BoxShape.circle,
                    ),
                    child: SvgPicture.asset(
                      prefixIcon,
                      width: prefixIconWidth,
                      height: prefixIconHeight,
                    ),
                  ),

                  SizedBox(width: gap),

                  Expanded(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context)
                              .textTheme
                              .labelMedium
                              ?.copyWith(
                            fontSize: titleFontSize,
                            fontWeight: FontWeight.w700,
                            height: 18 / titleFontSize,
                            color: AppColors.topSnackBarTitle,
                          ),
                        ),

                        SizedBox(height: responsiveGap),

                        Text(
                          message,
                          maxLines: 2,
                          overflow: TextOverflow.ellipsis,
                          style: Theme.of(context)
                              .textTheme
                              .bodySmall
                              ?.copyWith(
                            fontSize: messageFontSize,
                            fontWeight: FontWeight.w400,
                            height: responsiveTextHeight,
                            color: AppColors.topSnackBarMessage,
                          ),
                        ),
                      ],
                    ),
                  ),

                  SizedBox(width: 4 * widthScale),

                  GestureDetector(
                    behavior: HitTestBehavior.opaque,
                    onTap: onClose,
                    child: SvgPicture.asset(
                      postfixIcon,
                      width: postfixIconWidth,
                      height: postfixIconHeight,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}