import { useEffect, useState } from 'react';
import { KeyboardAvoidingView, Platform, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import { api, ApiError, newClientRequestId } from '../api';
import { useSession } from '../session';
import { colors, fonts, radius } from '../theme';
import { Banner, Button, Card, Header, text } from '../ui';

type Health = 'checking' | 'ok' | 'down';

export function JoinScreen() {
  const { apiUrl, save } = useSession();
  const [code, setCode] = useState<string>('');
  const [health, setHealth] = useState<Health>('checking');
  const [busy, setBusy] = useState<boolean>(false);
  const [error, setError] = useState<ApiError | null>(null);

  const checkHealth = async () => {
    if (!apiUrl) return;
    setHealth('checking');
    try {
      await api.health(apiUrl);
      setHealth('ok');
    } catch {
      setHealth('down');
    }
  };

  useEffect(() => {
    checkHealth();
    // Check the configured origin once when the screen opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apiUrl]);

  const join = async () => {
    if (!apiUrl) return;
    const joinCode = code.trim().toUpperCase();
    if (!joinCode) return;
    setBusy(true);
    setError(null);
    try {
      const joined = await api.join(apiUrl, joinCode);
      setHealth('ok');
      await save({
        apiUrl,
        token: joined.token,
        batchId: joined.batchId,
        tripDate: joined.tripDate,
        clientRequestId: newClientRequestId(),
        riderId: null,
        sentPayload: null,
      });
    } catch (e) {
      const err = e instanceof ApiError ? e : new ApiError('offline', String(e), 0);
      if (err.isNetwork) setHealth('down');
      setError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Header subtitle="Share a car home with students going your way." />
      <ScrollView contentContainerStyle={styles.body} keyboardShouldPersistTaps="handled">
        {!apiUrl ? (
          <Banner
            tone="error"
            title="Backend not configured"
            message="Set EXPO_PUBLIC_API_URL in artifacts/campus-connect/.env to the backend's HTTPS origin, then restart the mobile preview."
            testID="config-missing"
          />
        ) : health === 'down' ? (
          <Banner
            tone="error"
            title="Can't reach Yalla Ride"
            message={`Check your connection. The app is trying ${apiUrl}.`}
            actionLabel="Try again"
            onAction={checkHealth}
            testID="health-down"
          />
        ) : null}

        <Card>
          <Text style={text.h2}>Join today's rides</Text>
          <Text style={text.muted}>
            Enter the six-character code shown on the operator's Matching screen. It links this phone to that batch of rides.
          </Text>
          <TextInput
            value={code}
            onChangeText={(value) => setCode(value.replace(/[^A-Za-z0-9]/g, '').toUpperCase())}
            placeholder="ABC123"
            placeholderTextColor="#B9B9C2"
            autoCapitalize="characters"
            autoCorrect={false}
            maxLength={12}
            style={styles.code}
            returnKeyType="go"
            onSubmitEditing={join}
            accessibilityLabel="Join code"
            testID="join-code"
          />
          {error ? (
            <Banner
              tone={error.isNetwork ? 'error' : 'warning'}
              title={error.code === 'join_code_invalid' ? 'Code not recognised' : error.isNetwork ? "You're offline" : "Couldn't join"}
              message={error.message}
              testID="join-error"
            />
          ) : null}
          <Button label="Join" icon="enter-outline" onPress={join} busy={busy} disabled={!apiUrl || code.trim().length === 0} testID="join-submit" />
        </Card>

        <View style={styles.status}>
          <View style={[styles.dot, { backgroundColor: health === 'ok' ? colors.green : health === 'down' ? colors.red : colors.muted }]} />
          <Text style={text.muted} numberOfLines={1}>
            {apiUrl ? `${health === 'ok' ? 'Connected to' : health === 'down' ? 'Offline ·' : 'Checking'} ${apiUrl}` : 'No backend set'}
          </Text>
        </View>
        <Text style={[text.muted, styles.fine]}>Demo · simulated distances and fares · no real rides or payments</Text>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  body: { padding: 20, gap: 16 },
  code: {
    borderWidth: 1.5,
    borderColor: colors.line,
    borderRadius: radius.button,
    paddingVertical: 14,
    paddingHorizontal: 16,
    fontFamily: fonts.semibold,
    fontSize: 24,
    letterSpacing: 6,
    textAlign: 'center',
    color: colors.ink,
    backgroundColor: colors.background,
  },
  status: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 4 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  fine: { textAlign: 'center', fontSize: 11 },
});
