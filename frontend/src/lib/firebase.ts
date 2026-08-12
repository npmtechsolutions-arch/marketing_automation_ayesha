import { initializeApp, getApps, getApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithPopup } from "firebase/auth";

const firebaseConfig = {
  apiKey: "AIzaSyC9z6YeM9xCjZyG2CQsxJhnJfT8QfXN3EM",
  authDomain: "marketengine-ai.firebaseapp.com",
  projectId: "marketengine-ai",
  storageBucket: "marketengine-ai.firebasestorage.app",
  messagingSenderId: "647335947485",
  appId: "1:647335947485:web:2a72106b4e5ec3a103bf34",
  measurementId: "G-ELXL6YSWXN",
};

// Initialize Firebase only once
export const app = getApps().length === 0 ? initializeApp(firebaseConfig) : getApp();
export const auth = getAuth(app);

export const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({
  prompt: "select_account",
});

export async function signInWithGooglePopup() {
  const result = await signInWithPopup(auth, googleProvider);
  const user = result.user;
  const idToken = await user.getIdToken();
  return {
    user,
    idToken,
    email: user.email,
    displayName: user.displayName,
    photoURL: user.photoURL,
    uid: user.uid,
  };
}
