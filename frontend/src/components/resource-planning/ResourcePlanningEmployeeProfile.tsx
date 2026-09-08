import { useState } from 'react';
import { Stack, Typography } from '@mui/material';
import { useQuery } from '@tanstack/react-query';
import { fetchUserItProfile, itOperationsKeys } from '../../api/itOperations';
import { ITProfilePanel } from '../it/ITProfilePanel';
import { ProsohmButton } from '../ui/ProsohmButton';
import { DashboardPanel } from '../ui/design-system/DashboardPanel';
import { accessContextFromUser, canAssignItAssets } from '../../utils/permissions';
import { useAuth } from '../../context/AuthContext';
import { ResourcePackageAssignDialog } from './ResourcePackageAssignDialog';

type Props = {
  userId: string | null;
  userName?: string;
};

export function ResourcePlanningEmployeeProfile({ userId, userName }: Props) {
  const { user } = useAuth();
  const canAssign = canAssignItAssets(accessContextFromUser(user));
  const [assignOpen, setAssignOpen] = useState(false);

  const profileQuery = useQuery({
    queryKey: itOperationsKeys.profileUser(userId ?? ''),
    queryFn: () => fetchUserItProfile(userId as string),
    enabled: Boolean(userId),
  });

  if (!userId) {
    return (
      <DashboardPanel title="Employee resources">
        <Typography variant="body2" color="text.secondary">
          Select a person to see shift, hardware, software, and network from IT.
        </Typography>
      </DashboardPanel>
    );
  }

  return (
    <Stack spacing={2}>
      <DashboardPanel
        title="Employee resources"
        subtitle={userName}
        action={
          canAssign ? (
            <ProsohmButton size="small" onClick={() => setAssignOpen(true)}>
              Assign resources
            </ProsohmButton>
          ) : undefined
        }
      >
        <ITProfilePanel
          profile={profileQuery.data}
          loading={profileQuery.isLoading}
          emptyMessage="No shift, hardware, software, or IP assigned yet. The employee remains visible."
        />
      </DashboardPanel>
      <ResourcePackageAssignDialog
        open={assignOpen}
        userId={userId}
        userName={userName}
        onClose={() => setAssignOpen(false)}
      />
    </Stack>
  );
}
