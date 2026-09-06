class OtpResponseModel {
  final String message ;
  final double expiresTimeInMinutes ;

  OtpResponseModel({required  this.message , required this.expiresTimeInMinutes}) ;


factory OtpResponseModel.fromJson(Map<String , dynamic> json){
  return OtpResponseModel(
      message: json['message'], expiresTimeInMinutes: json['expires_in_minutes']);
}
}