import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { api, ApiError, BookingPayload, formatJod, Stop, StopsResponse } from '../api';
import { submitBooking } from '../booking';
import { Session, useSession } from '../session';
import { colors, fonts, radius } from '../theme';
import { Banner, Button, Card, Header, text, Toggle } from '../ui';

const STEP_MINUTES = 5;

function toMinutes(clock: string): number {
  const [h, m] = clock.split(':').map(Number);
  return h * 60 + m;
}

function toClock(minutes: number): string {
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
}

function asError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError('offline', String(e), 0);
}

/** Plain-language title for a booking failure. */
function bookingErrorTitle(error: ApiError): string {
  switch (error.code) {
    case 'offline':
    case 'timeout':
      return 'Booking not confirmed yet';
    case 'duplicate_name':
      return 'That name is taken';
    case 'batch_matched':
      return 'Booking is closed';
    case 'batch_full':
      return 'This batch is full';
    case 'request_conflict':
      return 'You already booked with other details';
    case 'already_booked':
      return 'This phone already booked';
    case 'invalid_input':
      return 'Check your details';
    default:
      return "Couldn't book";
  }
}

export function BookScreen({ session, onLeave }: { session: Session; onLeave: () => void }) {
  const { update } = useSession();
  const insets = useSafeAreaInsets();
  const pending = session.sentPayload;

  const [stops, setStops] = useState<StopsResponse | null>(null);
  const [stopsError, setStopsError] = useState<ApiError | null>(null);
  const [name, setName] = useState<string>(pending?.name ?? '');
  const [classEnd, setClassEnd] = useState<string>(pending?.classEnd ?? '16:00');
  const [stop, setStop] = useState<string>(pending?.stop ?? 'Dabouq');
  const [woman, setWoman] = useState<boolean>(pending?.woman ?? false);
  const [womenOnly, setWomenOnly] = useState<boolean>(pending?.womenOnly ?? false);
  const [busy, setBusy] = useState<boolean>(false);
  // While a booking is unresolved, only those exact details may be sent (see booking.ts).
  const locked = pending !== null || busy;
  const [error, setError] = useState<ApiError | null>(null);

  const loadStops = async () => {
    setStopsError(null);
    try {
      setStops(await api.stops(session.apiUrl));
    } catch (e) {
      setStopsError(asError(e));
    }
  };

  useEffect(() => {
    loadStops();
    // Load fares once when the screen opens; the retry button reloads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const earliest = toMinutes(stops?.rules.classEndEarliest ?? '08:00');
  const latest = toMinutes(stops?.rules.classEndLatest ?? '21:00');
  const shiftTime = (delta: number) => setClassEnd((current) => toClock(Math.min(latest, Math.max(earliest, toMinutes(current) + delta))));

  const selected = useMemo<{ stop: Stop; gate: string; corridor: string } | null>(() => {
    for (const corridor of stops?.corridors ?? []) {
      const found = corridor.stops.find((s) => s.name === stop);
      if (found) return { stop: found, gate: corridor.gate, corridor: corridor.name };
    }
    return null;
  }, [stops, stop]);

  const payload: BookingPayload = { name: name.trim().replace(/\s+/g, ' '), classEnd, stop, woman, womenOnly: woman && womenOnly };
  // An unresolved booking can always be resent with its stored details, even if drop-offs failed to load.
  const canSubmit = pending !== null || (payload.name.length >= 1 && payload.name.length <= 40 && !!selected);

  const send = async () => {
    setBusy(true);
    setError(null);
    const result = await submitBooking(
      {
        sentPayload: session.sentPayload,
        setSentPayload: (sentPayload) => update({ sentPayload }),
        setRider: (riderId) => update({ riderId, sentPayload: null }),
      },
      payload,
      (details) => api.book(session.apiUrl, session.token, session.batchId, details, session.clientRequestId),
    );
    setBusy(false);
    if (result.ok) {
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
      return;
    }
    if (result.error.code === 'unauthorized') {
      onLeave();
      return;
    }
    setError(result.error);
  };

  const errorAction = (): { label: string; run: () => void } | undefined => {
    if (!error) return undefined;
    if (pending) return { label: 'Retry booking', run: send };
    if (error.code === 'batch_matched' || error.code === 'already_booked' || error.code === 'request_conflict') {
      return { label: 'Join a different batch', run: onLeave };
    }
    return undefined;
  };
  const action = errorAction();

  return (
    <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
      <Header subtitle={`Ride home on ${session.tripDate}`} onLeave={onLeave} />
      <ScrollView contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + 32 }]} keyboardShouldPersistTaps="handled">
        {stopsError ? (
            <Banner
              tone="error"
              title={stopsError.isNetwork ? "You're offline" : "Couldn't load drop-offs"}
              message={stopsError.message}
              actionLabel="Try again"
              onAction={loadStops}
              testID="stops-error"
            />
        ) : null}
        <View pointerEvents={locked ? 'none' : 'auto'} style={[styles.form, locked && { opacity: 0.6 }]}>
        <Card>
          <Text style={text.label}>Your name</Text>
          <TextInput
            value={name}
            onChangeText={setName}
            placeholder="First name and initial"
            placeholderTextColor="#B9B9C2"
            maxLength={40}
            editable={!locked}
            autoCapitalize="words"
            style={styles.input}
            accessibilityLabel="Your name"
            testID="book-name"
          />
          <Text style={text.muted}>Other riders see only your first name.</Text>
        </Card>

        <Card>
          <Text style={text.label}>Class ends at</Text>
          <View style={styles.stepper}>
            <Pressable style={styles.stepBtn} onPress={() => shiftTime(-STEP_MINUTES)} accessibilityLabel="5 minutes earlier" testID="time-earlier">
              <Ionicons name="remove" size={22} color={colors.pink} />
            </Pressable>
            <Text style={styles.time} testID="class-end">{classEnd}</Text>
            <Pressable style={styles.stepBtn} onPress={() => shiftTime(STEP_MINUTES)} accessibilityLabel="5 minutes later" testID="time-later">
              <Ionicons name="add" size={22} color={colors.pink} />
            </Pressable>
          </View>
          <View style={styles.chips}>
            {['12:00', '14:00', '16:00', '18:00'].map((clock) => (
              <Pressable key={clock} onPress={() => setClassEnd(clock)} style={[styles.chip, classEnd === clock && styles.chipOn]}>
                <Text style={[styles.chipText, classEnd === clock && styles.chipTextOn]}>{clock}</Text>
              </Pressable>
            ))}
          </View>
          <Text style={text.muted}>Between {toClock(earliest)} and {toClock(latest)}. Pickup is about 15 minutes after class.</Text>
        </Card>

        <Card>
          <Text style={text.label}>Drop-off</Text>
          {stopsError ? (
            <Text style={text.muted}>Drop-offs couldn't load. Tap Try again above.</Text>
          ) : !stops ? (
            <ActivityIndicator color={colors.pink} style={{ paddingVertical: 20 }} />
          ) : (
            stops.corridors.map((corridor) => (
              <View key={corridor.name} style={{ gap: 6 }}>
                <Text style={styles.corridor}>
                  {corridor.name} · {corridor.gate}
                </Text>
                {corridor.stops.map((s) => {
                  const on = s.name === stop;
                  return (
                    <Pressable
                      key={s.name}
                      onPress={() => setStop(s.name)}
                      style={[styles.stop, on && styles.stopOn]}
                      accessibilityRole="radio"
                      accessibilityState={{ selected: on }}
                      testID={`stop-${s.name}`}
                    >
                      <Ionicons name={on ? 'radio-button-on' : 'radio-button-off'} size={20} color={on ? colors.pink : colors.muted} />
                      <View style={{ flex: 1 }}>
                        <Text style={styles.stopName}>{s.name}</Text>
                        <Text style={text.muted}>{s.km} km</Text>
                      </View>
                      <View style={{ alignItems: 'flex-end' }}>
                        <Text style={styles.share}>~{formatJod(s.sampleShare)}</Text>
                        <Text style={styles.solo}>{formatJod(s.soloFare)} alone</Text>
                      </View>
                    </Pressable>
                  );
                })}
              </View>
            ))
          )}
        </Card>

        <Card>
          <Toggle
            label="I'm a woman student"
            value={woman}
            onChange={(value) => {
              setWoman(value);
              if (!value) setWomenOnly(false);
            }}
            testID="toggle-woman"
          />
          <Toggle
            label="Women-only car"
            hint={woman ? 'Only match me with other women students.' : 'Available to women students.'}
            value={woman && womenOnly}
            onChange={setWomenOnly}
            disabled={!woman}
            testID="toggle-women-only"
          />
        </Card>
        </View>

        {selected && stops ? (
          <Card style={styles.summary}>
            <Text style={text.h3}>
              {classEnd} · {selected.gate} → {selected.stop.name}
            </Text>
            <Text style={text.body}>
              Sharing with {stops.rules.sampleShareRiders} riders costs about <Text style={styles.strong}>{formatJod(selected.stop.sampleShare)}</Text>{' '}
              instead of {formatJod(selected.stop.soloFare)} alone. You see your exact share before you confirm.
            </Text>
          </Card>
        ) : null}

        {pending && !error ? (
          <Banner
            tone="warning"
            title="Your last booking didn't get an answer"
            message="Send it again to find out. It uses the same request, so you won't be booked twice. You can change your details once we know it wasn't saved."
            testID="pending-booking"
          />
        ) : null}
        {error ? (
          <Banner
            tone={error.isNetwork ? 'error' : 'warning'}
            title={bookingErrorTitle(error)}
            message={
              pending
                ? `${error.message} Retrying sends the same request, so you won't be booked twice.`
                : error.code === 'duplicate_name'
                  ? 'Someone in this batch already used that name. Add your surname initial.'
                  : error.message
            }
            actionLabel={action?.label}
            onAction={action?.run}
            testID="book-error"
          />
        ) : null}

        <Button
          label={pending ? 'Send booking again' : 'Book shared ride'}
          icon={pending ? 'refresh' : 'car-outline'}
          onPress={send}
          busy={busy}
          disabled={!canSubmit}
          testID="book-submit"
        />
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  body: { padding: 16, gap: 14 },
  form: { gap: 14 },
  input: {
    borderWidth: 1.5,
    borderColor: colors.line,
    borderRadius: radius.button,
    paddingVertical: 12,
    paddingHorizontal: 14,
    fontFamily: fonts.medium,
    fontSize: 16,
    color: colors.ink,
    backgroundColor: colors.background,
  },
  stepper: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  stepBtn: { width: 48, height: 48, borderRadius: 24, backgroundColor: colors.pinkSoft, alignItems: 'center', justifyContent: 'center' },
  time: { fontFamily: fonts.semibold, fontSize: 36, color: colors.ink, letterSpacing: 1 },
  chips: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  chip: { paddingVertical: 6, paddingHorizontal: 12, borderRadius: radius.pill, backgroundColor: colors.background },
  chipOn: { backgroundColor: colors.pink },
  chipText: { fontFamily: fonts.medium, fontSize: 13, color: colors.ink },
  chipTextOn: { color: colors.white },
  corridor: { fontFamily: fonts.semibold, fontSize: 13, color: colors.plum, marginTop: 6 },
  stop: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 14, borderWidth: 1, borderColor: colors.line },
  stopOn: { borderColor: colors.pink, backgroundColor: colors.pinkSoft },
  stopName: { fontFamily: fonts.medium, fontSize: 15, color: colors.ink },
  share: { fontFamily: fonts.semibold, fontSize: 14, color: colors.pink },
  solo: { fontFamily: fonts.regular, fontSize: 12, color: colors.muted, textDecorationLine: 'line-through' },
  summary: { backgroundColor: colors.pinkSoft, borderColor: colors.pinkSoft },
  strong: { fontFamily: fonts.semibold, color: colors.pink },
});
