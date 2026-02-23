2026-02-18 01:47:42.713 15384-15903 GoogleApiManager        com.example.mbtichatfriend           E  Failed to get service from broker. 
                                                                                                    java.lang.SecurityException: Unknown calling package name 'com.google.android.gms'.
                                                                                                    	at android.os.Parcel.createExceptionOrNull(Parcel.java:3355)
                                                                                                    	at android.os.Parcel.createException(Parcel.java:3339)
                                                                                                    	at android.os.Parcel.readException(Parcel.java:3322)
                                                                                                    	at android.os.Parcel.readException(Parcel.java:3264)
                                                                                                    	at beoy.a(:com.google.android.gms@260438035@26.04.38 (260400-867839860):36)
                                                                                                    	at bemz.z(:com.google.android.gms@260438035@26.04.38 (260400-867839860):143)
                                                                                                    	at bdtf.run(:com.google.android.gms@260438035@26.04.38 (260400-867839860):42)
                                                                                                    	at android.os.Handler.handleCallback(Handler.java:995)
                                                                                                    	at android.os.Handler.dispatchMessage(Handler.java:103)
                                                                                                    	at csuf.mz(:com.google.android.gms@260438035@26.04.38 (260400-867839860):1)
                                                                                                    	at csuf.dispatchMessage(:com.google.android.gms@260438035@26.04.38 (260400-867839860):5)
                                                                                                    	at android.os.Looper.loopOnce(Looper.java:273)
                                                                                                    	at android.os.Looper.loop(Looper.java:363)
                                                                                                    	at android.os.HandlerThread.run(HandlerThread.java:85)
2026-02-18 01:47:42.714 15384-15903 GoogleApiManager        com.example.mbtichatfriend           W  Not showing notification since connectionResult is not user-facing: ConnectionResult{statusCode=DEVELOPER_ERROR, resolution=null, message=null, clientMethodKey=null}
2026-02-18 01:47:45.981 15384-15898 Firestore               com.example.mbtichatfriend           W  (25.1.1) [WriteStream]: (74346e7) Stream closed with status: Status{code=NOT_FOUND, description=The database (default) does not exist for project mbtifriend-bcbce Please visit https://console.cloud.google.com/datastore/setup?project=mbtifriend-bcbce to add a Cloud Datastore or Cloud Firestore database. , cause=null}.
2026-02-18 01:47:56.352 15384-15898 Firestore               com.example.mbtichatfriend           W  (25.1.1) [WriteStream]: (74346e7) Stream closed with status: Status{code=NOT_FOUND, description=The database (default) does not exist for project mbtifriend-bcbce Please visit https://console.cloud.google.com/datastore/setup?project=mbtifriend-bcbce to add a Cloud Datastore or Cloud Firestore database. , cause=null}.
