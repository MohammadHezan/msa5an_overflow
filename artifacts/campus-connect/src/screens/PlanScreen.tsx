import { Ionicons } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, AppState, RefreshControl, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { api, ApiError, formatJod, isSessionLost, Plan, Rider, riderFromPlanChanged, RiderStatus } from '../api';
import { Session } from '../session';
import { colors, fonts, radius } from '../theme';
import { Banner, BannerTone, Button, Card, Header, Row, text } from '../ui';

/** How often the plan screen re-reads the rider while the app is open (matching or another rider's decline can change it). */
const POLL_MS = 10000;

type Notice = { tone: BannerTone; title: string; message?: string } | null;

const STATUS_COPY: Record<RiderStatus, { icon: keyof typeof Ionicons.glyphMap; title: string; body: string; tone: string }> = {
  waiting: {
    icon: 'hourglass-outline',
    title: 'Booked. Waiting for matching',
    body: "We group students after booking closes. This screen updates by itself when your car is ready.",
    tone: colors.plum,
  },
  review: { icon: 'people-outline', title: 'Review your shared ride', body: 'Check the plan and confirm your seat.', tone: colors.pink },
  no_match: {
    icon: 'person-outline',
    title: 'No shared car this time',
    body: 'Nobody heading your way finished class close enough to your time. You can still take a solo ride at the solo fare.',
    tone: colors.amber,
  },
  confirmed: { icon: 'checkmark-circle', title: "You're in", body: 'Your shared ride is confirmed. Meet the car at the gate.', tone: colors.green },
  solo_confirmed: { icon: 'checkmark-circle', title: 'Solo ride confirmed', body: 'Meet your car at the gate.', tone: colors.green },
  changed: {
    icon: 'alert-circle',
    title: 'Your plan changed',
    body: 'Another rider left this car, so your share, pickup time or riders changed. Review and confirm again.',
    tone: colors.amber,
  },
  declined: { icon: 'close-circle', title: 'You left this ride', body: 'Your seat was released and the other riders were re-planned.', tone: colors.muted },
};

function asError(e: unknown): ApiError {
  return e instanceof ApiError ? e : new ApiError('offline', String(e), 0);
}

export function PlanScreen({ session, onLeave }: { session: Session; onLeave: () => void }) {
  const insets = useSafeAreaInsets();
  const riderId = session.riderId as number;
  const [rider, setRider] = useState<Rider | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [acting, setActing] = useState<'confirm' | 'decline' | null>(null);
  const [askDecline, setAskDecline] = useState<boolean>(false);
  const [notice, setNotice] = useState<Notice>(null);
  const inFlight = useRef<boolean>(false);

  const refresh = useCallback(
    async (manual = false) => {
      if (inFlight.current) return;
      inFlight.current = true;
      if (manual) setRefreshing(true);
      try {
        const next = await api.rider(session.apiUrl, session.token, riderId);
        setRider(next);
        setLoadError(null);
      } catch (e) {
        setLoadError(asError(e));
      } finally {
        inFlight.current = false;
        if (manual) setRefreshing(false);
      }
    },
    [session.apiUrl, session.token, riderId],
  );

  // Load on open, poll while open, and reload whenever the app returns to the foreground.
  useEffect(() => {
    refresh();
    const timer = setInterval(() => {
      if (AppState.currentState === 'active') refresh();
    }, POLL_MS);
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') refresh();
    });
    return () => {
      clearInterval(timer);
      sub.remove();
    };
  }, [refresh]);

  const confirm = async (plan: Plan) => {
    setActing('confirm');
    setNotice(null);
    try {
      const next = await api.confirm(session.apiUrl, session.token, riderId, plan.signature);
      setRider(next);
      setLoadError(null);
      Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => undefined);
    } catch (e) {
      const changed = riderFromPlanChanged(e);
      const err = asError(e);
      if (changed) {
        setRider(changed);
        setNotice({ tone: 'warning', title: 'The plan changed before you confirmed', message: 'Here is the updated plan. Check it and confirm again.' });
        Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning).catch(() => undefined);
      } else if (err.isNetwork) {
        setNotice({ tone: 'error', title: "Couldn't confirm", message: `${err.message} Your confirmation may not have been saved.` });
      } else {
        setNotice({ tone: 'warning', title: "Couldn't confirm", message: err.message });
        refresh();
      }
    } finally {
      setActing(null);
    }
  };

  const decline = async () => {
    setActing('decline');
    setNotice(null);
    try {
      const next = await api.decline(session.apiUrl, session.token, riderId);
      setRider(next);
      setAskDecline(false);
      setLoadError(null);
    } catch (e) {
      const err = asError(e);
      setNotice({
        tone: err.isNetwork ? 'error' : 'warning',
        title: "Couldn't leave the ride",
        message: err.isNetwork ? `${err.message} Trying again is safe.` : err.message,
      });
      if (!err.isNetwork) refresh();
    } finally {
      setActing(null);
    }
  };

  const sessionLost = isSessionLost(loadError);

  return (
    <View style={{ flex: 1 }}>
      <Header subtitle={rider ? `${rider.name} · ride home on ${rider.tripDate}` : `Ride home on ${session.tripDate}`} onLeave={onLeave} />
      <ScrollView
        contentContainerStyle={[styles.body, { paddingBottom: insets.bottom + 32 }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => refresh(true)} tintColor={colors.pink} colors={[colors.pink]} />}
      >
        {loadError && !sessionLost ? (
          <Banner
            tone="error"
            title={loadError.isNetwork ? "You're offline" : "Couldn't update your plan"}
            message={rider ? `${loadError.message} Showing the last plan we received.` : loadError.message}
            actionLabel="Try again"
            onAction={() => refresh(true)}
            testID="plan-offline"
          />
        ) : null}
        {sessionLost ? (
          <Banner
            tone="warning"
            title="This booking is no longer available"
            message="The operator may have started a new batch. Join again with the new code."
            actionLabel="Join with a new code"
            onAction={onLeave}
            testID="plan-session-lost"
          />
        ) : null}

        {!rider && !loadError ? <ActivityIndicator color={colors.pink} size="large" style={{ marginTop: 40 }} /> : null}

        {rider ? (
          <>
            <StatusCard rider={rider} />
            {notice ? <Banner tone={notice.tone} title={notice.title} message={notice.message} testID="plan-notice" /> : null}
            {rider.plan && rider.status !== 'declined' ? <PlanDetails rider={rider} plan={rider.plan} /> : <RequestDetails rider={rider} />}
            <Actions
              rider={rider}
              acting={acting}
              askDecline={askDecline}
              onConfirm={() => rider.plan && confirm(rider.plan)}
              onAskDecline={setAskDecline}
              onDecline={decline}
              onRefresh={() => refresh(true)}
              refreshing={refreshing}
              onLeave={onLeave}
            />
          </>
        ) : null}
      </ScrollView>
    </View>
  );
}

function StatusCard({ rider }: { rider: Rider }) {
  const copy = STATUS_COPY[rider.status];
  return (
    <Card style={{ flexDirection: 'row', alignItems: 'flex-start', gap: 14 }}>
      <View style={[styles.statusIcon, { backgroundColor: `${copy.tone}1A` }]}>
        <Ionicons name={copy.icon} size={26} color={copy.tone} />
      </View>
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={[text.h3, { color: copy.tone }]} testID="plan-status">
          {copy.title}
        </Text>
        <Text style={text.muted}>{copy.body}</Text>
      </View>
    </Card>
  );
}

function RequestDetails({ rider }: { rider: Rider }) {
  return (
    <Card>
      <Text style={text.label}>Your request</Text>
      <Row icon="time-outline" label="Class ends" value={rider.request.classEnd} />
      <Row icon="location-outline" label="Drop-off" value={rider.request.stop} />
      {rider.request.womenOnly ? <Row icon="female-outline" label="Matching" value="Women-only" /> : null}
      <Row icon="wallet-outline" label="Solo fare" value={formatJod(rider.soloFare)} />
    </Card>
  );
}

function PlanDetails({ rider, plan }: { rider: Rider; plan: Plan }) {
  return (
    <>
      <Card>
        <View style={styles.badges}>
          <Badge label={plan.shared ? `Shared · ${plan.dropOffs.length} riders` : 'Solo ride'} />
          {plan.womenOnly ? <Badge label="Women-only" /> : null}
          <Badge label={`${plan.corridor} corridor`} muted />
        </View>
        <Row icon="flag-outline" label="Meet at" value={plan.gate} strong />
        <Row icon="time-outline" label="Pickup" value={`${plan.pickupTime} · ${rider.tripDate}`} strong />
        {plan.shared ? <Row icon="people-outline" label="Riding with" value={plan.riders.join(', ')} /> : null}
      </Card>

      <Card>
        <Text style={text.label}>Drop-off order</Text>
        <View>
          <TimelineItem first label={plan.gate} detail={`Pickup ${plan.pickupTime}`} gate />
          {plan.dropOffs.map((d, i) => (
            <TimelineItem
              key={`${d.order}-${d.stop}`}
              order={d.order}
              label={d.stop}
              detail={d.you ? 'You' : d.rider}
              you={d.you}
              last={i === plan.dropOffs.length - 1}
            />
          ))}
        </View>
      </Card>

      <Card style={styles.priceCard}>
        <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end' }}>
          <View>
            <Text style={[text.label, { color: '#FFC4E4' }]}>{plan.shared ? 'Your share' : 'Solo fare'}</Text>
            <Text style={styles.price} testID="plan-share">
              {formatJod(plan.share)}
            </Text>
          </View>
          {plan.shared ? (
            <View style={{ alignItems: 'flex-end' }}>
              <Text style={styles.soloStrike}>{formatJod(plan.soloFare)} alone</Text>
              {plan.saving.fils > 0 ? <Text style={styles.saving}>You save {formatJod(plan.saving)}</Text> : null}
            </View>
          ) : null}
        </View>
        <Text style={[text.muted, { color: '#FFC4E4' }]}>Simulated fare. No payment is taken in this demo.</Text>
      </Card>
    </>
  );
}

function Actions({
  rider,
  acting,
  askDecline,
  onConfirm,
  onAskDecline,
  onDecline,
  onRefresh,
  refreshing,
  onLeave,
}: {
  rider: Rider;
  acting: 'confirm' | 'decline' | null;
  askDecline: boolean;
  onConfirm: () => void;
  onAskDecline: (value: boolean) => void;
  onDecline: () => void;
  onRefresh: () => void;
  refreshing: boolean;
  onLeave: () => void;
}) {
  const busy = acting !== null;
  if (rider.status === 'waiting') {
    return <Button label="Check for my car" icon="refresh" variant="secondary" onPress={onRefresh} busy={refreshing} testID="plan-refresh" />;
  }
  if (rider.status === 'declined') {
    return <Button label="Join with a new code" icon="enter-outline" variant="secondary" onPress={onLeave} testID="plan-rejoin" />;
  }
  const needsConfirm = rider.status === 'review' || rider.status === 'no_match' || rider.status === 'changed';
  const confirmLabel = rider.status === 'no_match' ? 'Take the solo ride' : rider.status === 'changed' ? 'Confirm updated plan' : 'Confirm my seat';

  return (
    <View style={{ gap: 10 }}>
      {needsConfirm ? (
        <Button label={confirmLabel} icon="checkmark" onPress={onConfirm} busy={acting === 'confirm'} disabled={busy} testID="plan-confirm" />
      ) : null}
      {askDecline ? (
        <Card style={{ borderColor: '#F3C4C4' }}>
          <Text style={text.h3}>Leave this ride?</Text>
          <Text style={text.muted}>
            {rider.plan?.shared
              ? 'Your seat is released and the other riders get a new plan. You will need a new join code to book again.'
              : 'Your ride is cancelled. You will need a new join code to book again.'}
          </Text>
          <Button label="Yes, leave ride" icon="close" variant="danger" onPress={onDecline} busy={acting === 'decline'} disabled={busy} testID="plan-decline-yes" />
          <Button label="Keep my seat" variant="secondary" onPress={() => onAskDecline(false)} disabled={busy} testID="plan-decline-no" />
        </Card>
      ) : (
        <Button
          label={rider.status === 'no_match' ? 'No thanks' : 'Decline'}
          icon="close"
          variant="danger"
          onPress={() => onAskDecline(true)}
          disabled={busy}
          testID="plan-decline"
        />
      )}
    </View>
  );
}

function Badge({ label, muted }: { label: string; muted?: boolean }) {
  return (
    <View style={[styles.badge, muted && { backgroundColor: colors.background }]}>
      <Text style={[styles.badgeText, muted && { color: colors.muted }]}>{label}</Text>
    </View>
  );
}

function TimelineItem({
  label,
  detail,
  order,
  first,
  last,
  you,
  gate,
}: {
  label: string;
  detail: string;
  order?: number;
  first?: boolean;
  last?: boolean;
  you?: boolean;
  gate?: boolean;
}) {
  return (
    <View style={styles.tlRow}>
      <View style={styles.tlRail}>
        <View style={[styles.tlLine, { opacity: first ? 0 : 1 }]} />
        <View style={[styles.tlDot, gate && styles.tlGate, you && styles.tlYou]}>
          {gate ? <Ionicons name="flag" size={12} color={colors.white} /> : <Text style={[styles.tlNum, you && { color: colors.white }]}>{order}</Text>}
        </View>
        <View style={[styles.tlLine, { opacity: last ? 0 : 1 }]} />
      </View>
      <View style={styles.tlText}>
        <Text style={[styles.tlLabel, you && { color: colors.pink }]}>{label}</Text>
        <Text style={text.muted}>{detail}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  body: { padding: 16, gap: 14 },
  statusIcon: { width: 46, height: 46, borderRadius: 23, alignItems: 'center', justifyContent: 'center' },
  badges: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  badge: { backgroundColor: colors.pinkSoft, paddingVertical: 4, paddingHorizontal: 10, borderRadius: radius.pill },
  badgeText: { fontFamily: fonts.medium, fontSize: 12, color: colors.pink },
  priceCard: { backgroundColor: colors.plum, borderColor: colors.plum },
  price: { fontFamily: fonts.bold, fontSize: 32, color: colors.white },
  soloStrike: { fontFamily: fonts.regular, fontSize: 13, color: '#FFB9DE', textDecorationLine: 'line-through' },
  saving: { fontFamily: fonts.semibold, fontSize: 14, color: colors.white, marginTop: 2 },
  tlRow: { flexDirection: 'row', minHeight: 52 },
  tlRail: { width: 28, alignItems: 'center' },
  tlLine: { flex: 1, width: 2, backgroundColor: colors.pinkSoft },
  tlDot: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 2,
    borderColor: colors.pink,
    backgroundColor: colors.white,
    alignItems: 'center',
    justifyContent: 'center',
  },
  tlGate: { backgroundColor: colors.pink },
  tlYou: { backgroundColor: colors.pink },
  tlNum: { fontFamily: fonts.semibold, fontSize: 11, color: colors.pink },
  tlText: { flex: 1, paddingLeft: 12, justifyContent: 'center' },
  tlLabel: { fontFamily: fonts.medium, fontSize: 15, color: colors.ink },
});
