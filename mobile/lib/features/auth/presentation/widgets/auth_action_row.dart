import 'package:flutter/material.dart';

import '../../../../config/theme/app_colors.dart';


class AuthActionRow extends StatelessWidget {
  final String message;
  final String actionText;
  final Color? messageColor;
  final Color? actionColor;
  final double textFontSize;
  final double gap ;
  final VoidCallback onActionPressed;

  const AuthActionRow({
    super.key,
    required this.message,
    required this.actionText,
    required this.onActionPressed,
    this.messageColor,
    this.actionColor,
    this.textFontSize = 14 ,
    this.gap = 4
  });

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: [
        Text(
          message,
          textAlign: TextAlign.center,
          style: textTheme.bodySmall?.copyWith(
            color: messageColor ??
                AppColors.white.withValues(alpha: 0.47),
            fontSize: textFontSize,
            height: 20 / 14,
            fontWeight: FontWeight.w400,
          ),
        ),
        TextButton(
          onPressed: onActionPressed,
          style: TextButton.styleFrom(
            foregroundColor: actionColor ?? AppColors.white,
            padding:  EdgeInsets.symmetric(
              horizontal:gap ,
              vertical: gap),
            minimumSize: Size.zero,
            tapTargetSize: MaterialTapTargetSize.shrinkWrap,
          ),
          child: Text(
            actionText,
            style: textTheme.bodySmall?.copyWith(
              color: actionColor ?? AppColors.white,
              fontSize: textFontSize,
              height: 20 / 14,
              fontWeight: FontWeight.w500,
            ),
          ),
        ),
      ],
    );
  }
}