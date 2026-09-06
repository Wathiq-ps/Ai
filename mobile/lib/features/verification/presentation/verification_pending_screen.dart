import 'package:flutter/material.dart';

class VerificationPendingScreen extends StatelessWidget {
  const VerificationPendingScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // ==========================
          // Background
          // ==========================
          Positioned.fill(
            child: Image.asset(
              'assets/images/onboarding_background.jpg',
              fit: BoxFit.cover,
            ),
          ),

          // طبقة غامقة فوق الخلفية
          Positioned.fill(
            child: Container(color: const Color(0xff001B4D).withOpacity(0.55)),
          ),

          // ==========================
          // Verification Pending Card
          // ==========================
          Align(
            alignment: Alignment.bottomCenter,
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.fromLTRB(15, 50, 15, 15),
              decoration: const BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.only(
                  topLeft: Radius.circular(45),
                  topRight: Radius.circular(45),
                ),
              ),
              child: SafeArea(
                top: false,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // ==========================
                    // Circle
                    // ==========================
                    Container(
                      width: 90,
                      height: 90,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: Colors.white,
                        border: Border.all(
                          color: const Color(0xff001B4D),
                          width: 4,
                        ),
                        boxShadow: [
                          BoxShadow(
                            color: Colors.grey.withOpacity(0.15),
                            blurRadius: 12,
                            spreadRadius: 2,
                          ),
                        ],
                      ),
                    ),

                    const SizedBox(height: 20),

                    // ==========================
                    // Title
                    // ==========================
                    const Text(
                      'Verification Pending',
                      textAlign: TextAlign.center,
                      style: TextStyle(
                        color: Color(0xff001B4D),
                        fontSize: 34,
                        fontWeight: FontWeight.w700,
                      ),
                    ),

                    const SizedBox(height: 10),

                    // ==========================
                    // Description
                    // ==========================
                    SizedBox(
                      width: 300,
                      child: const Text(
                        "We're reviewing your documents. This usually takes 1-2 business days. We'll notify you once it's approved.",

                        textAlign: TextAlign.center,
                        style: TextStyle(
                          color: Color(0xff001B4D),
                          fontSize: 16,
                          height: 1.6,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),

                    const SizedBox(height: 20),

                    // ==========================
                    // Back To Home
                    // ==========================
                    SizedBox(
                      width: double.infinity,
                      height: 65,
                      child: ElevatedButton(
                        onPressed: () {},
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xff001B4D),
                          foregroundColor: Colors.white,
                          elevation: 5,
                          shadowColor: Colors.black.withOpacity(0.3),
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(35),
                          ),
                        ),
                        child: const Text(
                          'Back to Home',
                          style: TextStyle(
                            fontSize: 19,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                      ),
                    ),

                    const SizedBox(height: 25),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
