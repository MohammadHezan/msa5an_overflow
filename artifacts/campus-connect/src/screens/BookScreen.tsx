import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import {
  api,
  ApiError,
  BookingPayload,
  formatJod,
  FriendsChoice,
  Gender,
  onlyLabel,
  onlyPreference,
  Preference,
  rideOptions,
  Stop,
  StopsResponse,
} from '../api';
import { submitBooking } from '../booking';
import { Session, useSession } from '../session';
import { colors, fonts, radius } from '../theme';
import { Banner, Button, Card, Header, Segmented, text, Toggle } from '../ui';

type FriendsMode = 'none' | 'start' | 'join';

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
    case 'group_not_found':
      return 'No group with that code';
    case 'group_full':
      return 'That group is full';
    case 'group_mismatch':
      return "You can't ride with that group";
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
  // Gender comes from the student's profile; the only "only" option offered matches it.
  const gender: Gender = session.student?.gender ?? (pending ? rideOptions(pending).gender : 'man');
  const only = onlyPreference(gender);
  const [preference, setPreference] = useState<Preference>(() => {
    const saved = pending ? rideOptions(pending).preference : 'mixed';
    return saved === only ? only : 'mixed';
  });
  const [friendsMode, setFriendsMode] = useState<FriendsMode>(pending?.friends?.mode ?? 'none');
  const [groupOpen, setGroupOpen] = useState<boolean>(pending?.friends?.mode === 'start' ? pending.friends.open : true);
  const [groupCode, setGroupCode] = useState<string>(pending?.friends?.mode === 'join' ? pending.friends.code : '');
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
    // Sessions saved before profiles carried a gender: fetch it once.
    if (session.student && !session.student.gender) {
      api.me(session.apiUrl, session.token)
        .then((me) => (me.student ? update({ student: me.student }) : undefined))
        .catch(() => undefined);
    }
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

  const code = groupCode.trim().toUpperCase();
  const friends: FriendsChoice | null =
    friendsMode === 'start' ? { mode: 'start', open: groupOpen } : friendsMode === 'join' ? { mode: 'join', code } : null;
  const payload: BookingPayload = { name: name.trim().replace(/\s+/g, ' '), classEnd, stop, gender, preference, friends };
  // An unresolved booking can always be resent with its stored details, even if drop-offs failed to load.
  const canSubmit =
    pending !== null ||
    (payload.name.length >= 1 && payload.name.length <= 40 && !!selected && (friendsMode !== 'join' || code.length > 0));

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
    if (error.code === 'batch_matched' && friendsMode !== 'none') {
      return {
        label: 'Book just me',
        run: () => {
          setFriendsMode('none');
          setError(null);
        },
      };
    }
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
          <Text style={text.label}>Ride with</Text>
          <Segmented
            label="Ride with"
            options={[
              { value: 'mixed' as Preference, label: 'Anyone' },
              { value: only, label: onlyLabel(only) },
            ]}
            value={preference}
            onChange={setPreference}
            testID="ride-with"
          />
          <Text style={text.muted}>
            {preference === 'mixed' ? 'The captain may be any gender.' : `Only ${gender === 'woman' ? 'women' : 'men'} students share your car. Matching may take longer.`}
          </Text>
        </Card>

        <Card>
          <Text style={text.label}>Book with friends</Text>
          <Segmented
            label="Book with friends"
            options={[
              { value: 'none' as FriendsMode, label: 'Just me' },
              { value: 'start' as FriendsMode, label: 'Start a group' },
              { value: 'join' as FriendsMode, label: 'Join a group' },
            ]}
            value={friendsMode}
            onChange={setFriendsMode}
            testID="friends"
          />
          {friendsMode === 'start' ? (
            <>
              <Toggle
                label="Let others fill empty seats"
                hint={groupOpen ? 'Other students may join your car.' : 'Only your group rides in the car.'}
                value={groupOpen}
                onChange={setGroupOpen}
                testID="toggle-group-open"
              />
              <Text style={text.muted}>You get a group code after booking. Share it so friends can join.</Text>
            </>
          ) : friendsMode === 'join' ? (
            <>
              <TextInput
                value={groupCode}
                onChangeText={(value) => setGroupCode(value.toUpperCase())}
                placeholder="GR-48"
                placeholderTextColor="#B9B9C2"
                maxLength={10}
                editable={!locked}
                autoCapitalize="characters"
                autoCorrect={false}
                style={styles.input}
                accessibilityLabel="Group code"
                testID="group-code"
              />
              <Text style={text.muted}>Ask a friend for their code. Friends in a group always ride in one car.</Text>
            </>
          ) : (
            <Text style={text.muted}>Friends in a group always ride in one car.</Text>
          )}
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
