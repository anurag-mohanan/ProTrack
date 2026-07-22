import { alpha, createTheme, type ThemeOptions } from '@mui/material/styles';
import {
  prosohmColors,
  prosohmColorsDark,
  type ProsohmColorMode,
} from './prosohmColors';

declare module '@mui/material/styles' {
  interface Palette {
    accent: Palette['primary'];
    prosohm: {
      sidebar: string;
      sidebarDark: string;
      sidebarText: string;
      sidebarTextMuted: string;
      sidebarActive: string;
      sidebarDivider: string;
      header: string;
      surface: string;
      card: string;
      border: string;
      hover: string;
      selected: string;
      accent: string;
      shadowCard: string;
      shadowCardHover: string;
      shadowHeader: string;
      shadowDialog: string;
      gradientLogin: string;
      gradientSidebar: string;
    };
  }
  interface PaletteOptions {
    accent?: PaletteOptions['primary'];
    prosohm?: {
      sidebar?: string;
      sidebarDark?: string;
      sidebarText?: string;
      sidebarTextMuted?: string;
      sidebarActive?: string;
      sidebarDivider?: string;
      header?: string;
      surface?: string;
      card?: string;
      border?: string;
      hover?: string;
      selected?: string;
      accent?: string;
      shadowCard?: string;
      shadowCardHover?: string;
      shadowHeader?: string;
      shadowDialog?: string;
      gradientLogin?: string;
      gradientSidebar?: string;
    };
  }
  interface TypographyVariants {
    pageTitle: React.CSSProperties;
    sectionTitle: React.CSSProperties;
    cardTitle: React.CSSProperties;
    tableHeader: React.CSSProperties;
    captionLabel: React.CSSProperties;
  }
  interface TypographyVariantsOptions {
    pageTitle?: React.CSSProperties;
    sectionTitle?: React.CSSProperties;
    cardTitle?: React.CSSProperties;
    tableHeader?: React.CSSProperties;
    captionLabel?: React.CSSProperties;
  }
}

declare module '@mui/material/Typography' {
  interface TypographyPropsVariantOverrides {
    pageTitle: true;
    sectionTitle: true;
    cardTitle: true;
    tableHeader: true;
    captionLabel: true;
  }
}

declare module '@mui/material/Button' {
  interface ButtonPropsColorOverrides {
    accent: true;
  }
}

function buildPalette(mode: ProsohmColorMode) {
  const colors = mode === 'dark' ? prosohmColorsDark : prosohmColors;
  const shadowBase = colors.secondary.main;

  return {
    mode,
    primary: colors.primary,
    secondary: colors.secondary,
    success: colors.success,
    warning: colors.warning,
    error: colors.error,
    info: colors.info,
    accent: colors.accent,
    text: {
      primary: colors.neutral.textPrimary,
      secondary: colors.neutral.textSecondary,
      disabled: colors.neutral.textMuted,
    },
    background: {
      default: colors.neutral.background,
      paper: colors.neutral.surface,
    },
    divider: colors.neutral.divider,
    prosohm: {
      sidebar: colors.neutral.sidebar,
      sidebarDark: colors.neutral.sidebarDark,
      sidebarText: colors.neutral.textOnDark,
      sidebarTextMuted: colors.neutral.textOnDarkMuted,
      sidebarActive: colors.neutral.sidebarActive,
      sidebarDivider: colors.neutral.sidebarDivider,
      header: colors.neutral.header,
      surface: colors.neutral.surface,
      card: colors.neutral.card,
      border: colors.neutral.border,
      hover: colors.neutral.hover,
      selected: colors.neutral.selected,
      accent: colors.accent.main,
      shadowCard: `0 8px 24px ${alpha(shadowBase, colors.shadow.card)}`,
      shadowCardHover: `0 12px 28px ${alpha(shadowBase, colors.shadow.cardHover)}`,
      shadowHeader: `0 4px 20px ${alpha(shadowBase, colors.shadow.header)}`,
      shadowDialog: `0 24px 48px ${alpha(shadowBase, colors.shadow.dialog)}`,
      gradientLogin: `linear-gradient(160deg, ${colors.neutral.sidebar} 0%, ${colors.secondary.dark} 55%, ${colors.primary.dark} 100%)`,
      gradientSidebar: `linear-gradient(180deg, ${colors.neutral.sidebarOverlayTop} 0%, ${colors.neutral.sidebarOverlayBottom} 100%)`,
    },
  } as const;
}

function buildTypography() {
  const fontFamily = '"Inter", "Segoe UI", "Roboto", "Helvetica", "Arial", sans-serif';

  return {
    fontFamily,
    h1: { fontFamily, fontWeight: 700, fontSize: '2.25rem', lineHeight: 1.2 },
    h2: { fontFamily, fontWeight: 700, fontSize: '1.875rem', lineHeight: 1.25 },
    h3: { fontFamily, fontWeight: 700, fontSize: '1.5rem', lineHeight: 1.3 },
    h4: { fontFamily, fontWeight: 700, fontSize: '1.25rem', lineHeight: 1.35 },
    h5: { fontFamily, fontWeight: 600, fontSize: '1.125rem', lineHeight: 1.4 },
    h6: { fontFamily, fontWeight: 600, fontSize: '1rem', lineHeight: 1.45 },
    subtitle1: { fontFamily, fontWeight: 600, fontSize: '0.9375rem', lineHeight: 1.5 },
    subtitle2: { fontFamily, fontWeight: 600, fontSize: '0.8125rem', lineHeight: 1.5 },
    body1: { fontFamily, fontWeight: 400, fontSize: '0.9375rem', lineHeight: 1.6 },
    body2: { fontFamily, fontWeight: 400, fontSize: '0.875rem', lineHeight: 1.6 },
    button: {
      fontFamily,
      fontWeight: 600,
      fontSize: '0.875rem',
      lineHeight: 1.5,
      textTransform: 'none' as const,
    },
    caption: { fontFamily, fontWeight: 500, fontSize: '0.75rem', lineHeight: 1.5 },
    overline: {
      fontFamily,
      fontWeight: 700,
      fontSize: '0.6875rem',
      lineHeight: 1.6,
      letterSpacing: '0.08em',
      textTransform: 'uppercase' as const,
    },
    pageTitle: {
      fontFamily,
      fontWeight: 700,
      fontSize: '1.75rem',
      lineHeight: 1.25,
      letterSpacing: '-0.02em',
    },
    sectionTitle: {
      fontFamily,
      fontWeight: 700,
      fontSize: '1.125rem',
      lineHeight: 1.35,
    },
    cardTitle: {
      fontFamily,
      fontWeight: 600,
      fontSize: '0.875rem',
      lineHeight: 1.45,
    },
    tableHeader: {
      fontFamily,
      fontWeight: 700,
      fontSize: '0.75rem',
      lineHeight: 1.5,
      letterSpacing: '0.04em',
      textTransform: 'uppercase' as const,
    },
    captionLabel: {
      fontFamily,
      fontWeight: 500,
      fontSize: '0.75rem',
      lineHeight: 1.5,
    },
  };
}

function buildComponents(mode: ProsohmColorMode): ThemeOptions['components'] {
  const colors = mode === 'dark' ? prosohmColorsDark : prosohmColors;

  return {
    MuiCssBaseline: {
      styleOverrides: {
        html: {
          overflowX: 'clip',
        },
        body: {
          scrollbarColor: `${alpha(colors.primary.main, 0.4)} transparent`,
          overflowX: 'clip',
          maxWidth: '100%',
        },
        '#root': {
          minHeight: '100vh',
          maxWidth: '100%',
          overflowX: 'clip',
          '@supports (min-height: 100dvh)': {
            minHeight: '100dvh',
          },
        },
        img: {
          maxWidth: '100%',
          height: 'auto',
        },
      },
    },
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          borderRadius: 10,
          paddingInline: 18,
          paddingBlock: 9,
          fontWeight: 600,
          '&.MuiButton-containedPrimary:hover': {
            backgroundColor: colors.primary.dark,
          },
        },
        outlined: {
          borderWidth: 1.5,
          '&:hover': {
            borderWidth: 1.5,
          },
        },
        sizeSmall: {
          paddingInline: 14,
          paddingBlock: 6,
        },
        sizeLarge: {
          paddingInline: 24,
          paddingBlock: 12,
        },
      },
      variants: [
        {
          props: { color: 'accent' },
          style: {
            backgroundColor: colors.accent.main,
            color: colors.accent.contrastText,
            '&:hover': {
              backgroundColor: colors.accent.dark,
            },
          },
        },
      ],
    },
    MuiCard: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: {
          borderRadius: 16,
          border: `1px solid ${colors.neutral.border}`,
          backgroundColor: colors.neutral.card,
          boxShadow: `0 8px 24px ${alpha(colors.secondary.main, colors.shadow.card)}`,
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        rounded: {
          borderRadius: 16,
        },
        outlined: {
          borderColor: colors.neutral.border,
        },
      },
    },
    MuiAppBar: {
      defaultProps: {
        elevation: 0,
      },
      styleOverrides: {
        root: {
          backgroundColor: colors.neutral.header,
          color: colors.neutral.textPrimary,
          borderBottom: `1px solid ${colors.neutral.border}`,
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          borderRight: 'none',
        },
      },
    },
    MuiListItemButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          marginInline: 12,
          marginBlock: 2,
          '&.Mui-selected': {
            backgroundColor: alpha(colors.primary.main, 0.18),
            color: colors.neutral.textOnDark,
            '& .MuiListItemIcon-root': {
              color: colors.primary.main,
            },
            '&:hover': {
              backgroundColor: alpha(colors.primary.main, 0.24),
            },
          },
          '&:hover': {
            backgroundColor: alpha(colors.neutral.textOnDark, 0.06),
          },
        },
      },
    },
    MuiTextField: {
      defaultProps: {
        variant: 'outlined',
      },
    },
    MuiOutlinedInput: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          backgroundColor: colors.neutral.surface,
          '&:hover .MuiOutlinedInput-notchedOutline': {
            borderColor: alpha(colors.primary.main, 0.5),
          },
          '&.Mui-focused .MuiOutlinedInput-notchedOutline': {
            borderColor: colors.primary.main,
            borderWidth: 2,
          },
        },
        notchedOutline: {
          borderColor: colors.neutral.border,
        },
      },
    },
    MuiInputLabel: {
      styleOverrides: {
        root: {
          fontWeight: 500,
        },
        outlined: {
          // Keep clear of the input text while floating; stops label/value collision
          // when Select/Autocomplete values are long.
          '&.MuiInputLabel-shrink': {
            backgroundColor: colors.neutral.surface,
            paddingInline: 4,
            marginLeft: -2,
          },
        },
      },
    },
    MuiSelect: {
      defaultProps: {
        // Ensures empty Select fields still reserve notch space when a label is used.
      },
      styleOverrides: {
        select: {
          // Prevent selected MenuItem text from painting under a stuck label.
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        },
      },
    },
    MuiFormControl: {
      styleOverrides: {
        root: {
          // Outlined labels need vertical room so they can float above the value.
          '& .MuiInputLabel-outlined:not(.MuiInputLabel-shrink)': {
            maxWidth: 'calc(100% - 36px)',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
          },
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 20,
          boxShadow: `0 24px 48px ${alpha(colors.secondary.main, colors.shadow.dialog)}`,
        },
      },
    },
    MuiTabs: {
      styleOverrides: {
        root: {
          minHeight: 44,
          borderBottom: `1px solid ${colors.neutral.border}`,
        },
        indicator: {
          height: 3,
          borderRadius: '3px 3px 0 0',
        },
      },
    },
    MuiTab: {
      styleOverrides: {
        root: {
          textTransform: 'none',
          fontWeight: 600,
          fontSize: '0.875rem',
          minHeight: 44,
          '&.Mui-selected': {
            color: colors.primary.main,
          },
        },
      },
    },
    MuiChip: {
      styleOverrides: {
        root: {
          fontWeight: 600,
          borderRadius: 8,
        },
      },
    },
    MuiTableHead: {
      styleOverrides: {
        root: {
          backgroundColor: colors.neutral.borderLight,
          '& .MuiTableCell-head': {
            fontWeight: 700,
            fontSize: '0.75rem',
            letterSpacing: '0.04em',
            textTransform: 'uppercase',
            color: colors.neutral.textSecondary,
            borderBottom: `1px solid ${colors.neutral.border}`,
          },
        },
      },
    },
    MuiTableRow: {
      styleOverrides: {
        root: {
          '&:nth-of-type(even)': {
            backgroundColor: alpha(colors.neutral.borderLight, 0.45),
          },
          '&:hover': {
            backgroundColor: colors.neutral.hover,
          },
          '&:last-child td': {
            borderBottom: 0,
          },
        },
      },
    },
    MuiTableCell: {
      styleOverrides: {
        root: {
          borderColor: colors.neutral.border,
          paddingBlock: 14,
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 12,
        },
      },
    },
    MuiDivider: {
      styleOverrides: {
        root: {
          borderColor: colors.neutral.border,
        },
      },
    },
    MuiIconButton: {
      styleOverrides: {
        root: {
          borderRadius: 10,
          '&:hover': {
            backgroundColor: colors.neutral.hover,
          },
        },
      },
    },
  };
}

export function createProsohmTheme(mode: ProsohmColorMode = 'light') {
  return createTheme({
    palette: buildPalette(mode),
    typography: buildTypography(),
    shape: {
      borderRadius: 12,
    },
    spacing: 8,
    components: buildComponents(mode),
  });
}

export const prosohmTheme = createProsohmTheme('light');
