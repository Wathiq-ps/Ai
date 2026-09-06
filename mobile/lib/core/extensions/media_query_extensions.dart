import 'package:flutter/material.dart';

extension MediaQueryExtension on BuildContext {

  double get screenWidth => MediaQuery.sizeOf(this).width;
  double get screenHeight => MediaQuery.sizeOf(this).height;


  bool get isPortrait =>
      MediaQuery.orientationOf(this) == Orientation.portrait;

  bool get isLandscape =>
      MediaQuery.orientationOf(this) == Orientation.landscape;


  double get topPadding => MediaQuery.paddingOf(this).top;
  double get bottomPadding => MediaQuery.paddingOf(this).bottom;
  double get leftPadding => MediaQuery.paddingOf(this).left;
  double get rightPadding => MediaQuery.paddingOf(this).right;

  double get textScaleFactor => MediaQuery.textScalerOf(this).scale(1.0);
}