import { Poppins_400Regular, Poppins_500Medium, Poppins_600SemiBold, Poppins_700Bold, useFonts } from '@expo-google-fonts/poppins';
import { StatusBar } from 'expo-status-bar';
import * as SplashScreen from 'expo-splash-screen';
import { useEffect } from 'react';
import { ActivityIndicator, StyleSheet, View } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { BookScreen } from './src/screens/BookScreen';
import { JoinScreen } from './src/screens/JoinScreen';
import { PlanScreen } from './src/screens/PlanScreen';
import { VerifyScreen } from './src/screens/VerifyScreen';
import { SessionProvider, useSession } from './src/session';
import { colors } from './src/theme';

/** Join → Verify university → Book → Plan, chosen from what the phone has stored. */
function Root() {
  const { session, loaded, clear } = useSession();
  if (!loaded) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.pink} size="large" />
      </View>
    );
  }
  if (!session) return <JoinScreen />;
  // A phone that already booked keeps its plan; verification comes before a new booking.
  if (session.riderId === null && !session.verified) return <VerifyScreen session={session} onLeave={clear} />;
  if (session.riderId === null) return <BookScreen session={session} onLeave={clear} />;
  return <PlanScreen key={session.riderId} session={session} onLeave={clear} />;
}

export default function App() {
  const [fontsLoaded, fontError] = useFonts({ Poppins_400Regular, Poppins_500Medium, Poppins_600SemiBold, Poppins_700Bold });
  useEffect(() => {
    if (fontsLoaded || fontError) SplashScreen.hideAsync();
  }, [fontsLoaded, fontError]);
  // Render with system fonts if Poppins fails to load rather than staying blank.
  if (!fontsLoaded && !fontError) return null;
  return (
    <SafeAreaProvider>
      <SessionProvider>
        <View style={styles.app}>
          <StatusBar style="light" />
          <Root />
        </View>
      </SessionProvider>
    </SafeAreaProvider>
  );
}

const styles = StyleSheet.create({
  app: { flex: 1, backgroundColor: colors.background },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
});
