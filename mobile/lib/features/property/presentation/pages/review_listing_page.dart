import 'package:flutter/material.dart';

class ReviewListingPage extends StatelessWidget {
  const ReviewListingPage({super.key});

  // بيانات الإعلان
  final String listingType = 'For Sale';
  final String propertyType = 'Apartment';
  final String location = 'Gaza';
  final String area = '150 m²';
  final String price = '85,000 JOD';

  final String description =
      'Beautiful modern apartment in the heart of Al-Masyoun......';

  final List<String> features = const [
    '3 Rooms',
    '2 Bathrooms',
    'Elevator',
    'Parking',
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // =====================================================
          // Background
          // =====================================================
          Positioned.fill(
            child: Image.asset(
              'assets/images/background.png',
              fit: BoxFit.cover,
            ),
          ),

          // =====================================================
          // Dark blue overlay
          // =====================================================
          Positioned.fill(
            child: Container(color: const Color(0xFF00245F).withOpacity(0.78)),
          ),

          SafeArea(
            child: Column(
              children: [
                // =================================================
                // Header
                // =================================================
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 20, 20, 0),
                  child: Row(
                    children: [
                      // Back
                      GestureDetector(
                        onTap: () {
                          Navigator.pop(context);
                        },
                        child: const Icon(
                          Icons.arrow_back,
                          color: Colors.white,
                          size: 32,
                        ),
                      ),

                      const SizedBox(width: 20),

                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            const Text(
                              'Review your listing',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 29,
                                fontWeight: FontWeight.bold,
                              ),
                            ),

                            const SizedBox(height: 4),

                            Text(
                              'Step 6 of 6',
                              style: TextStyle(
                                color: Colors.white.withOpacity(0.75),
                                fontSize: 18,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),

                // =================================================
                // Content
                // =================================================
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.fromLTRB(20, 22, 20, 25),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // =========================================
                        // Photos
                        // =========================================
                        const Text(
                          'Photos',
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 21,
                            fontWeight: FontWeight.bold,
                          ),
                        ),

                        const SizedBox(height: 18),

                        SizedBox(
                          height: 205,
                          child: ListView(
                            scrollDirection: Axis.horizontal,
                            children: [
                              _propertyImage('assets/images/property1.jpg'),

                              const SizedBox(width: 15),

                              _propertyImage('assets/images/property2.jpg'),
                            ],
                          ),
                        ),

                        const SizedBox(height: 35),

                        // =========================================
                        // Basic Details
                        // =========================================
                        _sectionTitle(
                          title: 'Basic Details',
                          onEdit: () {
                            // افتح صفحة تعديل Basic Details
                          },
                        ),

                        const SizedBox(height: 10),

                        _detailRow('Listing Type', listingType),

                        _divider(),

                        _detailRow('Property Type', propertyType),

                        _divider(),

                        _detailRow('Location', location),

                        _divider(),

                        _detailRow('Area', area),

                        _divider(),

                        _detailRow('Price', price),

                        const SizedBox(height: 30),

                        // =========================================
                        // Features
                        // =========================================
                        _sectionTitle(
                          title: 'Features',
                          onEdit: () {
                            // تعديل الخصائص
                          },
                        ),

                        const SizedBox(height: 15),

                        GridView.builder(
                          shrinkWrap: true,
                          physics: const NeverScrollableScrollPhysics(),
                          itemCount: features.length,
                          gridDelegate:
                              const SliverGridDelegateWithFixedCrossAxisCount(
                                crossAxisCount: 2,
                                mainAxisSpacing: 16,
                                crossAxisSpacing: 10,
                                childAspectRatio: 4.5,
                              ),
                          itemBuilder: (context, index) {
                            return Text(
                              features[index],
                              style: const TextStyle(
                                color: Colors.white,
                                fontSize: 18,
                                fontWeight: FontWeight.w500,
                              ),
                            );
                          },
                        ),

                        const SizedBox(height: 30),

                        // =========================================
                        // Description
                        // =========================================
                        _sectionTitle(
                          title: 'Description',
                          onEdit: () {
                            // تعديل الوصف
                          },
                        ),

                        const SizedBox(height: 14),

                        Padding(
                          padding: const EdgeInsets.symmetric(horizontal: 10),
                          child: Text(
                            description,
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                            style: TextStyle(
                              color: Colors.white.withOpacity(0.82),
                              fontSize: 18,
                              height: 1.5,
                            ),
                          ),
                        ),

                        const SizedBox(height: 35),

                        // =========================================
                        // Continue
                        // =========================================
                        SizedBox(
                          width: double.infinity,
                          height: 72,
                          child: ElevatedButton(
                            onPressed: () {
                              _submitListing(context);
                            },
                            style: ElevatedButton.styleFrom(
                              backgroundColor: const Color(0xFF00194D),
                              foregroundColor: Colors.white,
                              elevation: 0,
                              shape: RoundedRectangleBorder(
                                borderRadius: BorderRadius.circular(40),
                              ),
                            ),
                            child: const Text(
                              'Continue',
                              style: TextStyle(
                                fontSize: 21,
                                fontWeight: FontWeight.bold,
                              ),
                            ),
                          ),
                        ),

                        const SizedBox(height: 10),
                      ],
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  // =============================================================
  // Property Image
  // =============================================================

  Widget _propertyImage(String imagePath) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(17),
      child: SizedBox(
        width: 330,
        height: 205,
        child: Image.asset(imagePath, fit: BoxFit.cover),
      ),
    );
  }

  // =============================================================
  // Section Title
  // =============================================================

  Widget _sectionTitle({required String title, required VoidCallback onEdit}) {
    return Row(
      children: [
        Text(
          title,
          style: const TextStyle(
            color: Colors.white,
            fontSize: 21,
            fontWeight: FontWeight.bold,
          ),
        ),

        const Spacer(),

        GestureDetector(
          onTap: onEdit,
          child: Row(
            children: [
              Icon(
                Icons.edit_outlined,
                color: Colors.white.withOpacity(0.7),
                size: 23,
              ),

              const SizedBox(width: 5),

              Text(
                'Edit',
                style: TextStyle(
                  color: Colors.white.withOpacity(0.7),
                  fontSize: 17,
                ),
              ),
            ],
          ),
        ),
      ],
    );
  }

  // =============================================================
  // Detail Row
  // =============================================================

  Widget _detailRow(String title, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 11, horizontal: 10),
      child: Row(
        children: [
          Expanded(
            child: Text(
              title,
              style: TextStyle(
                color: Colors.white.withOpacity(0.75),
                fontSize: 18,
              ),
            ),
          ),

          Text(
            value,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  // =============================================================
  // Divider
  // =============================================================

  Widget _divider() {
    return Container(height: 1, color: Colors.white.withOpacity(0.10));
  }

  // =============================================================
  // Submit
  // =============================================================

  void _submitListing(BuildContext context) {
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Listing submitted successfully')),
    );

    // هنا لاحقًا:
    //
    // إرسال بيانات الإعلان إلى Laravel API
    //
    // مثال:
    // await repository.createListing(...);
  }
}
