import { Ionicons } from '@expo/vector-icons';
import { ReactNode, useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { api, ApiError, isSessionLost, University, VerificationChallenge } from '../api';
import { Session, useSession } from '../session';
import { colors, fonts, radius } from '../theme';
import { Banner, Button, Card, Header, text } from '../ui';
import { cleanCode, CODE_DIGITS, formatCountdown, looksLikeEmail, needsNewCode, secondsUntil, verificationErrorTitle } from '../verification';

type Step = 'choose' | 'email' | 'unavailable' | 'code';

function asError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError('offline', String(e), 0);
}

/** Choose a campus → enter university email → enter the six-digit code (screens 04, 02 and 03 of the design). */
export function VerifyScreen({ session, onLeave }: { session: Session; onLeave: () => void }) {
  const { update } = useSession();
  const insets = useSafeAreaInsets();
  const pending = session.verification;

  const [step, setStep] = useState<Step>(pending ? 'code' : 'choose');
  const [search, setSearch] = useState<string>('');
  const [universities, setUniversities] = useState<University[] | null>(null);
  const [listError, setListError] = useState<ApiError | null>(null);
  const [chosen, setChosen] = useState<University | null>(null);
  const [email, setEmail] = useState<string>('');
  const [code, setCode] = useState<string>('');
  const [busy, setBusy] = useState<'send' | 'resend' | 'confirm' | 'notify' | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [notified, setNotified] = useState<Record<number, string>>({});
  const [now, setNow] = useState<number>(Date.now());

  const loadUniversities = useCallback(
    async (term: string) => {
      setListError(null);
      try {
        setUniversities(await api.universities(session.apiUrl, session.token, term.trim()));
      } catch (e) {
        setListError(asError(e));
      }
    },
    [session.apiUrl, session.token],
  );

  // Search as the student types, waiting briefly so each keystroke is not a request.
  useEffect(() => {
    if (step !== 'choose') return;
    const timer = setTimeout(() => loadUniversities(search), search ? 250 : 0);
    return () => clearTimeout(timer);
  }, [search, step, loadUniversities]);

  // Tick once a second while a code is outstanding so expiry and resend countdowns stay current.
  useEffect(() => {
    if (step !== 'code') return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [step]);

  const fail = (e: unknown) => setError(asError(e));

  const pick = (university: University) => {
    setChosen(university);
    setError(null);
    setNotice(null);
    setStep(university.available ? 'email' : 'unavailable');
  };

  const remember = async (university: { id: number; name: string }, challenge: VerificationChallenge) => {
    await update({
      verification: {
        universityId: university.id,
        universityName: university.name,
        maskedEmail: challenge.maskedEmail,
        expiresAt: challenge.expiresAt,
        resendAvailableAt: challenge.resendAvailableAt,
      },
    });
    setNow(Date.now());
  };

  const send = async () => {
    if (!chosen || !looksLikeEmail(email)) return;
    setBusy('send');
    setError(null);
    setNotice(null);
    try {
      const result = await api.startVerification(session.apiUrl, session.token, chosen.id, email.trim());
      if ('alreadyVerified' in result) {
        await update({ verified: true, student: result.student, verification: null });
        return;
      }
      await remember(chosen, result);
      setCode('');
      setStep('code');
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const resend = async () => {
    if (!pending) return;
    setBusy('resend');
    setError(null);
    setNotice(null);
    try {
      const result = await api.resendVerification(session.apiUrl, session.token);
      await remember({ id: pending.universityId, name: pending.universityName }, result);
      setCode('');
      setNotice(result.message ?? 'New code sent');
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const confirm = async () => {
    if (code.length !== CODE_DIGITS) return;
    setBusy('confirm');
    setError(null);
    setNotice(null);
    try {
      const result = await api.confirmVerification(session.apiUrl, session.token, code);
      // The server issues a new student token tied to the verified profile.
      await update({ token: result.token, verified: true, student: result.student, verification: null });
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const notify = async () => {
    if (!chosen) return;
    setBusy('notify');
    setError(null);
    try {
      const result = await api.notifyUniversity(session.apiUrl, session.token, chosen.id);
      setNotified((current) => ({ ...current, [chosen.id]: result.message }));
    } catch (e) {
      fail(e);
    } finally {
      setBusy(null);
    }
  };

  const differentEmail = async () => {
    await update({ verification: null });
    setCode('');
    setError(null);
    setNotice(null);
    setStep(chosen ? 'email' : 'choose');
  };

  const back = () => {
    setError(null);
    setNotice(null);
    setStep('choose');
  };

  const errorBanner = error ? (
    isSessionLost(error) ? (
      <Banner tone="error" title="This session has ended" message={error.message} actionLabel="Join with a new code" onAction={onLeave} testID="verify-session-lost" />
    ) : (
      <Banner tone={error.isNetwork ? 'error' : 'warning'} title={verificationErrorTitle(error)} message={error.message} testID="verify-error" />
    )
  ) : null;

  const backLink = (
    <Pressable onPress={back} hitSlop={8} style={styles.back} testID="verify-back">
      <Ionicons name="chevron-back" size={18} color={colors.pink} />
      <Text style={styles.link}>Choose another campus</Text>
    </Pressable>
  );

  let body: ReactNode;
  if (step === 'choose') {
    body = (
      <Card>
        <Text style={text.label}>Student access</Text>
        <Text style={text.h2}>Choose your university</Text>
        <Text style={text.muted}>Start with the campus you're leaving from.</Text>
        <View style={styles.searchBox}>
          <Ionicons name="search" size={18} color={colors.muted} />
          <TextInput
            value={search}
            onChangeText={setSearch}
            placeholder="University or city"
            placeholderTextColor="#B9B9C2"
            autoCorrect={false}
            maxLength={100}
            style={styles.searchInput}
            accessibilityLabel="Search universities"
            testID="university-search"
          />
        </View>
        {listError ? (
          isSessionLost(listError) ? (
            <Banner tone="error" title="This session has ended" message={listError.message} actionLabel="Join with a new code" onAction={onLeave} testID="verify-session-lost" />
          ) : (
            <Banner
              tone="error"
              title={listError.isNetwork ? "You're offline" : "Couldn't load campuses"}
              message={listError.message}
              actionLabel="Try again"
              onAction={() => loadUniversities(search)}
              testID="universities-error"
            />
          )
        ) : !universities ? (
          <ActivityIndicator color={colors.pink} style={{ paddingVertical: 20 }} />
        ) : universities.length === 0 ? (
          <Text style={text.muted} testID="universities-empty">No campus matches "{search.trim()}".</Text>
        ) : (
          universities.map((u) => (
            <Pressable key={u.id} onPress={() => pick(u)} style={({ pressed }) => [styles.option, pressed && { opacity: 0.7 }]} testID={`university-${u.id}`}>
              <View style={[styles.optionIcon, !u.available && { backgroundColor: colors.line }]}>
                <Ionicons name="school-outline" size={20} color={u.available ? colors.pink : colors.muted} />
              </View>
              <View style={{ flex: 1 }}>
                <Text style={text.h3}>{u.name}</Text>
                <Text style={text.muted}>
                  {u.available ? `${u.campus} · ${u.gate} pickup` : `${u.city} · Campus service updates`}
                </Text>
                <Text style={[styles.availability, { color: u.available ? colors.green : colors.amber }]}>
                  {u.available ? 'Available for this route' : notified[u.id] ? "We'll keep you posted" : 'Get notified when available'}
                </Text>
              </View>
              <Ionicons name="chevron-forward" size={18} color={colors.muted} />
            </Pressable>
          ))
        )}
      </Card>
    );
  } else if (step === 'unavailable' && chosen) {
    const message = notified[chosen.id];
    body = (
      <>
        <Card>
          <Text style={text.label}>Coming to more campuses</Text>
          <Text style={text.h2}>Your campus is next in line.</Text>
          <Text style={text.muted}>Yalla Ride is not available at {chosen.name} yet.</Text>
          <Banner tone="info" title="Stay in the loop" message="Get a service update in your Jeeny notifications when this campus is available." />
          {message ? <Banner tone="success" title={message} message={`Request saved for ${chosen.name}.`} testID="notify-confirmed" /> : null}
          {errorBanner}
          {message ? null : <Button label="Notify me in Jeeny" icon="notifications-outline" onPress={notify} busy={busy === 'notify'} testID="notify-me" />}
          <Button label="Choose another campus" variant="secondary" onPress={back} testID="choose-another" />
        </Card>
        <Text style={[text.muted, styles.fine]}>Regular Jeeny rides are still available.</Text>
      </>
    );
  } else if (step === 'email' && chosen) {
    const valid = looksLikeEmail(email);
    body = (
      <>
        <Card>
          <Text style={text.label}>Student access</Text>
          <Text style={text.h2}>Share with your campus</Text>
          <Text style={text.muted}>Verify once using your university email.</Text>
          <View style={styles.chosen}>
            <Ionicons name="school-outline" size={18} color={colors.pink} />
            <Text style={[text.body, { flex: 1 }]}>
              {chosen.name} · {chosen.campus}
            </Text>
          </View>
          <Text style={text.label}>University email</Text>
          <TextInput
            value={email}
            onChangeText={setEmail}
            placeholder="name@university.edu"
            placeholderTextColor="#B9B9C2"
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType="email-address"
            textContentType="emailAddress"
            maxLength={254}
            style={styles.input}
            returnKeyType="send"
            onSubmitEditing={send}
            accessibilityLabel="University email"
            testID="verify-email"
          />
          {errorBanner}
          <Button label="Send verification code" icon="mail-outline" onPress={send} busy={busy === 'send'} disabled={!valid} testID="verify-send" />
          {backLink}
        </Card>
        <Banner tone="info" title="Your student community" message="University verification keeps shared rides for students. Your email stays private." />
      </>
    );
  } else if (pending) {
    const expiresIn = secondsUntil(pending.expiresAt, now);
    const resendIn = secondsUntil(pending.resendAvailableAt, now);
    const blocked = expiresIn === 0 || (error !== null && needsNewCode(error));
    body = (
      <>
        <Card>
          <Text style={text.label}>Student access</Text>
          <Text style={text.h2}>Check your university email</Text>
          <Text style={text.muted} testID="verify-masked">
            Enter the {CODE_DIGITS}-digit code sent to {pending.maskedEmail}.
          </Text>
          <TextInput
            value={code}
            onChangeText={(value) => setCode(cleanCode(value))}
            placeholder="••••••"
            placeholderTextColor="#B9B9C2"
            keyboardType="number-pad"
            textContentType="oneTimeCode"
            autoComplete="one-time-code"
            maxLength={CODE_DIGITS}
            style={styles.code}
            returnKeyType="done"
            onSubmitEditing={confirm}
            accessibilityLabel="Verification code"
            testID="verify-code"
          />
          <Text style={[styles.timer, expiresIn === 0 && { color: colors.red }]} testID="verify-expiry">
            {expiresIn > 0 ? `Code expires in ${formatCountdown(expiresIn)}` : 'Code expired. Request a new one.'}
          </Text>
          {notice ? <Banner tone="success" title={notice} message={`Sent to ${pending.maskedEmail}.`} testID="verify-notice" /> : null}
          {errorBanner}
          <Button
            label="Verify & continue"
            icon="checkmark-circle-outline"
            onPress={confirm}
            busy={busy === 'confirm'}
            disabled={code.length !== CODE_DIGITS || blocked}
            testID="verify-confirm"
          />
          <Button
            label={resendIn > 0 ? `Resend code in ${formatCountdown(resendIn)}` : 'Resend code'}
            variant="secondary"
            icon="refresh-outline"
            onPress={resend}
            busy={busy === 'resend'}
            disabled={resendIn > 0}
            testID="verify-resend"
          />
          <Pressable onPress={differentEmail} hitSlop={8} style={styles.back} testID="verify-different-email">
            <Text style={styles.link}>Use a different email</Text>
          </Pressable>
        </Card>
        <Banner
          tone="warning"
          title="Demo: no email is sent"
          message="The code is printed in the Yalla Ride server console. Other students see your first name and verification badge, never your email."
          testID="verify-demo-note"
        />
      </>
    );
  } else {
    body = null;
  }

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Header subtitle={pending?.universityName ?? chosen?.name ?? 'Verify your student email'} onLeave={onLeave} />
      <ScrollView contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + 32 }]} keyboardShouldPersistTaps="handled">
        {body}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  body: { padding: 20, gap: 16 },
  searchBox: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    borderWidth: 1.5,
    borderColor: colors.line,
    borderRadius: radius.button,
    paddingHorizontal: 12,
    backgroundColor: colors.background,
  },
  searchInput: { flex: 1, paddingVertical: 12, fontFamily: fonts.regular, fontSize: 15, color: colors.ink },
  option: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.line },
  optionIcon: { width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.pinkSoft },
  availability: { fontFamily: fonts.medium, fontSize: 12, marginTop: 2 },
  chosen: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 12, borderRadius: radius.button, backgroundColor: colors.pinkSoft },
  input: {
    borderWidth: 1.5,
    borderColor: colors.line,
    borderRadius: radius.button,
    paddingVertical: 12,
    paddingHorizontal: 14,
    fontFamily: fonts.regular,
    fontSize: 15,
    color: colors.ink,
    backgroundColor: colors.background,
  },
  code: {
    borderWidth: 1.5,
    borderColor: colors.line,
    borderRadius: radius.button,
    paddingVertical: 14,
    fontFamily: fonts.semibold,
    fontSize: 26,
    letterSpacing: 10,
    textAlign: 'center',
    color: colors.ink,
    backgroundColor: colors.background,
  },
  timer: { fontFamily: fonts.medium, fontSize: 13, color: colors.muted, textAlign: 'center' },
  back: { flexDirection: 'row', alignItems: 'center', alignSelf: 'center', gap: 4, paddingVertical: 4 },
  link: { fontFamily: fonts.semibold, fontSize: 14, color: colors.pink },
  fine: { textAlign: 'center', fontSize: 12 },
});
