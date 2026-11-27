import { Ionicons } from '@expo/vector-icons';
import { ReactNode } from 'react';
import { ActivityIndicator, Image, Platform, Pressable, StyleSheet, Text, View, ViewStyle } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors, fonts, radius } from './theme';

type IconName = keyof typeof Ionicons.glyphMap;

export function Header({ subtitle, onLeave }: { subtitle?: string; onLeave?: () => void }) {
  const insets = useSafeAreaInsets();
  const top = Platform.OS === 'web' ? Math.max(insets.top, 16) : insets.top;
  return (
    <View style={[styles.header, { paddingTop: top + 10 }]}>
      <View style={styles.headerRow}>
        <Image source={require('../assets/jeeny-logo.png')} style={styles.logo} resizeMode="contain" accessibilityLabel="Jeeny" />
        {onLeave ? (
          <Pressable onPress={onLeave} hitSlop={10} accessibilityLabel="Leave this demo session" testID="leave-session" style={styles.leave}>
            <Ionicons name="log-out-outline" size={20} color={colors.white} />
          </Pressable>
        ) : null}
      </View>
      <Text style={styles.headerTitle}>Yalla Ride</Text>
      {subtitle ? <Text style={styles.headerSubtitle}>{subtitle}</Text> : null}
    </View>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: ViewStyle }) {
  return <View style={[styles.card, style]}>{children}</View>;
}

export function Button({
  label,
  onPress,
  icon,
  variant = 'primary',
  busy = false,
  disabled = false,
  testID,
}: {
  label: string;
  onPress: () => void;
  icon?: IconName;
  variant?: 'primary' | 'secondary' | 'danger';
  busy?: boolean;
  disabled?: boolean;
  testID?: string;
}) {
  const inactive = disabled || busy;
  const tint = variant === 'primary' ? colors.white : variant === 'danger' ? colors.red : colors.pink;
  return (
    <Pressable
      onPress={onPress}
      disabled={inactive}
      testID={testID}
      accessibilityRole="button"
      accessibilityState={{ disabled: inactive, busy }}
      style={({ pressed }) => [
        styles.button,
        variant === 'primary' && styles.buttonPrimary,
        variant === 'secondary' && styles.buttonSecondary,
        variant === 'danger' && styles.buttonDanger,
        pressed && !inactive && { opacity: 0.8, transform: [{ scale: 0.98 }] },
        inactive && { opacity: 0.5 },
      ]}
    >
      {busy ? <ActivityIndicator color={tint} /> : icon ? <Ionicons name={icon} size={18} color={tint} /> : null}
      <Text style={[styles.buttonLabel, { color: tint }]}>{label}</Text>
    </Pressable>
  );
}

export type BannerTone = 'error' | 'warning' | 'info' | 'success';

export function Banner({
  tone,
  title,
  message,
  actionLabel,
  onAction,
  testID,
}: {
  tone: BannerTone;
  title: string;
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
  testID?: string;
}) {
  const palette = {
    error: { bg: colors.redSoft, fg: colors.red, icon: 'cloud-offline-outline' as IconName },
    warning: { bg: colors.amberSoft, fg: colors.amber, icon: 'alert-circle-outline' as IconName },
    info: { bg: colors.pinkSoft, fg: colors.plum, icon: 'information-circle-outline' as IconName },
    success: { bg: colors.greenSoft, fg: colors.green, icon: 'checkmark-circle-outline' as IconName },
  }[tone];
  return (
    <View style={[styles.banner, { backgroundColor: palette.bg }]} testID={testID} accessibilityRole="alert">
      <Ionicons name={palette.icon} size={22} color={palette.fg} />
      <View style={{ flex: 1 }}>
        <Text style={[styles.bannerTitle, { color: palette.fg }]}>{title}</Text>
        {message ? <Text style={styles.bannerText}>{message}</Text> : null}
        {actionLabel && onAction ? (
          <Pressable onPress={onAction} hitSlop={8} style={styles.bannerAction} testID={testID ? `${testID}-action` : undefined}>
            <Text style={[styles.bannerActionText, { color: palette.fg }]}>{actionLabel}</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

export function Toggle({
  label,
  hint,
  value,
  onChange,
  disabled = false,
  testID,
}: {
  label: string;
  hint?: string;
  value: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
  testID?: string;
}) {
  return (
    <Pressable
      onPress={() => !disabled && onChange(!value)}
      disabled={disabled}
      style={[styles.toggleRow, disabled && { opacity: 0.45 }]}
      accessibilityRole="switch"
      accessibilityState={{ checked: value, disabled }}
      testID={testID}
    >
      <View style={{ flex: 1 }}>
        <Text style={styles.toggleLabel}>{label}</Text>
        {hint ? <Text style={styles.muted}>{hint}</Text> : null}
      </View>
      <View style={[styles.track, value && styles.trackOn]}>
        <View style={[styles.thumb, value && styles.thumbOn]} />
      </View>
    </Pressable>
  );
}

export function Row({ icon, label, value, strong }: { icon: IconName; label: string; value: string; strong?: boolean }) {
  return (
    <View style={styles.row}>
      <Ionicons name={icon} size={18} color={colors.pink} />
      <Text style={styles.rowLabel}>{label}</Text>
      <Text style={[styles.rowValue, strong && { fontFamily: fonts.semibold }]}>{value}</Text>
    </View>
  );
}

export const text = StyleSheet.create({
  h2: { fontFamily: fonts.semibold, fontSize: 20, color: colors.ink },
  h3: { fontFamily: fonts.semibold, fontSize: 16, color: colors.ink },
  body: { fontFamily: fonts.regular, fontSize: 14, color: colors.ink, lineHeight: 21 },
  muted: { fontFamily: fonts.regular, fontSize: 13, color: colors.muted, lineHeight: 19 },
  label: { fontFamily: fonts.medium, fontSize: 12, color: colors.muted, letterSpacing: 0.6, textTransform: 'uppercase' },
});

const styles = StyleSheet.create({
  header: { backgroundColor: colors.pink, paddingHorizontal: 20, paddingBottom: 22, borderBottomLeftRadius: 28, borderBottomRightRadius: 28 },
  headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  logo: { width: 84, height: 22, tintColor: colors.white },
  leave: { padding: 6, borderRadius: radius.pill, backgroundColor: 'rgba(255,255,255,0.18)' },
  headerTitle: { marginTop: 14, fontFamily: fonts.bold, fontSize: 26, color: colors.white },
  headerSubtitle: { fontFamily: fonts.regular, fontSize: 14, color: '#FFD9EE', marginTop: 2 },
  card: { backgroundColor: colors.surface, borderRadius: radius.card, padding: 18, gap: 12, borderWidth: 1, borderColor: colors.line },
  button: {
    minHeight: 50,
    borderRadius: radius.button,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 8,
    paddingHorizontal: 18,
  },
  buttonPrimary: { backgroundColor: colors.pink },
  buttonSecondary: { backgroundColor: colors.pinkSoft },
  buttonDanger: { backgroundColor: colors.surface, borderWidth: 1, borderColor: '#F3C4C4' },
  buttonLabel: { fontFamily: fonts.semibold, fontSize: 15 },
  banner: { flexDirection: 'row', gap: 10, padding: 14, borderRadius: 14, alignItems: 'flex-start' },
  bannerTitle: { fontFamily: fonts.semibold, fontSize: 14 },
  bannerText: { fontFamily: fonts.regular, fontSize: 13, color: colors.ink, marginTop: 2, lineHeight: 19 },
  bannerAction: { marginTop: 8, alignSelf: 'flex-start' },
  bannerActionText: { fontFamily: fonts.semibold, fontSize: 13, textDecorationLine: 'underline' },
  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 6 },
  toggleLabel: { fontFamily: fonts.medium, fontSize: 14, color: colors.ink },
  muted: { fontFamily: fonts.regular, fontSize: 12, color: colors.muted },
  track: { width: 46, height: 28, borderRadius: 14, backgroundColor: colors.line, padding: 3 },
  trackOn: { backgroundColor: colors.pink },
  thumb: { width: 22, height: 22, borderRadius: 11, backgroundColor: colors.white },
  thumbOn: { transform: [{ translateX: 18 }] },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  rowLabel: { fontFamily: fonts.regular, fontSize: 14, color: colors.muted, flex: 1 },
  rowValue: { fontFamily: fonts.medium, fontSize: 14, color: colors.ink, textAlign: 'right', flexShrink: 1 },
});
