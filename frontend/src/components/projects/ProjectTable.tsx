import { useMemo } from 'react';
import { Box } from '@mui/material';
import { DataGrid, type GridColDef } from '@mui/x-data-grid';
import { useNavigate } from 'react-router-dom';
import type { Customer, Project, Stream, User } from '../../types';
import { StatusChip } from '../common/StatusChip';
import { formatDate, formatNumber, userDisplayName } from '../../utils/format';

export interface ProjectTableRow extends Project {
  customerName: string;
  designLeaderName: string;
  designerName: string;
  surfacerName: string;
  streamName: string;
}

interface ProjectTableProps {
  projects: Project[];
  customers: Customer[];
  users: User[];
  streams: Stream[];
}

function buildNameMap<T extends { id: string }>(
  items: T[],
  getLabel: (item: T) => string,
): Map<string, string> {
  const map = new Map<string, string>();
  items.forEach((item) => map.set(item.id, getLabel(item)));
  return map;
}

export function buildProjectTableRows(
  projects: Project[],
  customers: Customer[],
  users: User[],
  streams: Stream[],
): ProjectTableRow[] {
  const customerMap = buildNameMap(customers, (item) => item.name);
  const userMap = buildNameMap(users, (item) => userDisplayName(item));
  const streamMap = buildNameMap(streams, (item) => item.name);

  return projects.map((project) => ({
    ...project,
    customerName: customerMap.get(project.customer_id) ?? '—',
    designLeaderName: userMap.get(project.design_leader_id) ?? '—',
    designerName: project.designer_id
      ? (userMap.get(project.designer_id) ?? '—')
      : '—',
    surfacerName: project.surfacer_id
      ? (userMap.get(project.surfacer_id) ?? '—')
      : '—',
    streamName: streamMap.get(project.stream_id) ?? '—',
  }));
}

export function ProjectTable({
  projects,
  customers,
  users,
  streams,
}: ProjectTableProps) {
  const navigate = useNavigate();

  const rows = useMemo(
    () => buildProjectTableRows(projects, customers, users, streams),
    [projects, customers, users, streams],
  );

  const columns: GridColDef<ProjectTableRow>[] = [
    { field: 'tool_number', headerName: 'Tool Number', flex: 1, minWidth: 130 },
    {
      field: 'part_description',
      headerName: 'Part Description',
      flex: 1.5,
      minWidth: 180,
    },
    { field: 'customerName', headerName: 'Customer', flex: 1, minWidth: 140 },
    {
      field: 'designLeaderName',
      headerName: 'Design Leader',
      flex: 1,
      minWidth: 140,
    },
    { field: 'designerName', headerName: 'Designer', flex: 1, minWidth: 120 },
    { field: 'surfacerName', headerName: 'Surfacer', flex: 1, minWidth: 120 },
    { field: 'streamName', headerName: 'Stream', flex: 1, minWidth: 120 },
    {
      field: 'due_date',
      headerName: 'Due Date',
      width: 120,
      valueFormatter: (value) => formatDate(String(value)),
    },
    {
      field: 'status',
      headerName: 'Status',
      width: 150,
      renderCell: (params) => <StatusChip status={params.value} />,
    },
    {
      field: 'quoted_hours',
      headerName: 'Quoted Hours',
      width: 130,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value) => formatNumber(Number(value)),
    },
  ];

  return (
    <Box sx={{ width: '100%' }}>
      <DataGrid
        rows={rows}
        columns={columns}
        autoHeight
        disableRowSelectionOnClick
        pageSizeOptions={[10, 25, 50]}
        initialState={{
          pagination: { paginationModel: { pageSize: 10 } },
        }}
        onRowClick={(params) => navigate(`/projects/${params.id}`)}
        sx={{
          border: 0,
          '& .MuiDataGrid-row': { cursor: 'pointer' },
        }}
      />
    </Box>
  );
}
