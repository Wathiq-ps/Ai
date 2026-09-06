class OtpRequestModel {
  final String email ;

  OtpRequestModel({required this.email});

  Map<String , String > toJson(){
    return{
      "email" : email
    } ;
  }
}