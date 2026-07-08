import ArrowBackRoundedIcon from '@mui/icons-material/ArrowBackRounded';
import { ProsohmButton } from '../ui/ProsohmButton';
import { useBackNavigation } from '../../hooks/useBackNavigation';

interface BackButtonProps {
  fallbackPath: string;
  label?: string;
}

export function BackButton({ fallbackPath, label = 'Back' }: BackButtonProps) {
  const { goBack } = useBackNavigation(fallbackPath);

  return (
    <ProsohmButton
      buttonVariant="outlined"
      size="small"
      startIcon={<ArrowBackRoundedIcon />}
      onClick={goBack}
      sx={{ alignSelf: 'flex-start', mb: 1 }}
    >
      {label}
    </ProsohmButton>
  );
}
