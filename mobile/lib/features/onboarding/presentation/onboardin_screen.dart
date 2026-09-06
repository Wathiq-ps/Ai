import 'package:flutter/cupertino.dart';
import 'package:flutter/material.dart';
import 'package:flutter_svg/svg.dart';
import 'package:go_router/go_router.dart';
import 'package:mobile/core/extensions/media_query_extensions.dart';
import '../../../config/routes/routes_names.dart';
import '../../../config/theme/app_colors.dart';
import '../../../core/constant/app_icons.dart';
import '../../../core/constant/images_path.dart';
import '../../../core/constant/strings.dart';
import '../../../core/widget/app_button.dart';
import '../../../core/widget/app_top_snackbar.dart';
import '../../auth/presentation/widgets/auth_action_row.dart';

class OnBoardingScreen extends StatelessWidget {
  const OnBoardingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;
    final _figmaWidth = 393 ;
    final _figmaHeight = 852 ;
    final _currentScreenWidth = context.screenWidth ;
    final _currentScreenHeight = context.screenHeight ;
    final _widthScale = (_currentScreenWidth / _figmaWidth) ;
    final _heightScale = (_currentScreenHeight / _figmaHeight);
    final _horizantalPadding = _widthScale * 32 ;


    return Scaffold(
      body: Stack(
            fit: StackFit.expand,
            children: [

              Positioned.fill(
                child: Image.asset(
                  ImagePath.background,
                  fit: BoxFit.fill,
                ),
              ),

              Positioned.fill(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    gradient: LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [
                        Colors.black.withValues(alpha: 0.10),
                        Colors.black.withValues(alpha: 0.50),
                        AppColors.backgroundGradient.withValues(alpha: 0.95),
                      ],
                    ),
                  ),
                ),
              ),


              Padding(
                padding:  EdgeInsets.symmetric(horizontal: _horizantalPadding),
                child: Column(
                  mainAxisAlignment: MainAxisAlignment.end,
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    Text(
                      AppStrings.onboardingTitle,
                      textAlign: TextAlign.center,
                      style: textTheme.headlineLarge?.copyWith(
                        color: AppColors.white,
                        fontSize: _heightScale * 36,
                        height:  (45 / 36),
                        fontWeight: FontWeight.w700,
                        letterSpacing: -0.9,
                      ),
                    ),

                     SizedBox(height: _heightScale *  16),

                     Text(
                        AppStrings.onboardingSubtitle,
                        textAlign: TextAlign.center,
                        style: textTheme.bodyLarge?.copyWith(
                          color: AppColors.secondary,
                          fontSize:_heightScale * 18,
                          height:  (28 / 18),
                          fontWeight: FontWeight.w500,
                        ),
                      ),

                    SizedBox(height: _heightScale * 64),

                    AppElevatedButton(
                      text: AppStrings.continueWithEmail,
                      onPressed: () {
                        context.push(
                          RouteNames.emailRegisterScreen,
                        );
                      },
                      backgroundColor: AppColors.white,
                      height: _heightScale * 56,
                      width: double.infinity,
                      borderRadius: 50,
                      preIcon: SvgPicture.asset(
                        AppIcons.gmail,
                        width: _widthScale * 20,
                        height: _widthScale *  20,
                        excludeFromSemantics: true,),
                      textStyle:
                      textTheme.bodyMedium?.copyWith(
                        fontSize: _widthScale * 16 ,
                        height: ( 24 / 16),
                        fontWeight: FontWeight.w500,
                        color: AppColors.textPrimary,
                      ),
                      iconGap: 13 * _widthScale,
                    ),

                     SizedBox(height: _heightScale *  16),

                    AppElevatedButton(
                      text: AppStrings.continueWithPhone,
                      onPressed: () {
                        AppTopSnackBar.show(
                          context,
                          title:AppStrings.featureNotAvailable ,
                          message: AppStrings.featureWillBeAvailbleLater,
                          prefixIcon: AppIcons.error,
                        );
                      },
                      backgroundColor: AppColors.transparent,
                      enableBorder: true,
                      borderColor:
                      AppColors.border.withValues(alpha: 0.5),
                      height: _heightScale *  56,
                      width: double.infinity,
                      borderRadius: 9999,
                      preIcon: SvgPicture.asset(
                        AppIcons.phone,
                        width: _widthScale * 20,
                        height: _widthScale * 20,
                        excludeFromSemantics: true,
                      ),
                      textStyle:
                      textTheme.bodyMedium?.copyWith(
                        fontSize: 16 * _widthScale,
                        height: 24 / 16,
                        fontWeight: FontWeight.w500,
                        color: AppColors.white,
                      ),
                      iconGap: 13 * _widthScale,
                    ),

                     SizedBox(height: _heightScale *   41),

                    AuthActionRow(
                      message: AppStrings.alreadyHaveAccount,
                      actionText: AppStrings.signIn,
                      messageColor: AppColors.white.withValues(alpha: 0.47),
                      actionColor: AppColors.white,
                      onActionPressed: () {
                        context.go(
                          RouteNames.onboardingLoginScreen,
                        );
                      },
                      textFontSize: 14 * _widthScale,
                      gap: 4 * _widthScale,
                    ),
                    SizedBox(height: _heightScale *   39),
                  ],
                ),
              ),
            ],
          )
    );
  }
}
