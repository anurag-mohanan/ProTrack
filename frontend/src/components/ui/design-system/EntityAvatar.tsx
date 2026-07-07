import { Avatar } from '@mui/material';
import { designTokens } from '../../../theme/designTokens';

const PALETTE = [
  designTokens.semantic.primary,
  designTokens.stage.preliminary.main,
  designTokens.stage.intermediate.main,
  designTokens.stage.final.main,
  designTokens.semantic.success,
  designTokens.semantic.warning,
];

function colorFromLabel(label: string): string {
  let hash = 0;
  for (let i = 0; i < label.length; i += 1) {
    hash = label.charCodeAt(i) + ((hash << 5) - hash);
  }
  return PALETTE[Math.abs(hash) % PALETTE.length];
}

function initialsFromLabel(label: string): string {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) return '?';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] ?? ''}${parts[1][0] ?? ''}`.toUpperCase();
}

interface EntityAvatarProps {
  label: string;
  size?: number;
}

export function EntityAvatar({ label, size = 28 }: EntityAvatarProps) {
  const color = colorFromLabel(label);
  return (
    <Avatar
      sx={{
        width: size,
        height: size,
        fontSize: size * 0.38,
        fontWeight: 700,
        bgcolor: `${color}22`,
        color,
        border: `1px solid ${color}44`,
      }}
    >
      {initialsFromLabel(label)}
    </Avatar>
  );
}
