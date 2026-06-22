import { useEffect, useState } from 'react';
import {
  customersApi,
  projectsApi,
  rolesApi,
  streamsApi,
  usersApi,
} from '../api/resources';
import { projectLabel } from '../types';

export function useLookupMaps() {
  const [customers, setCustomers] = useState<Record<string, string>>({});
  const [streams, setStreams] = useState<Record<string, string>>({});
  const [users, setUsers] = useState<Record<string, string>>({});
  const [projects, setProjects] = useState<Record<string, string>>({});
  const [roles, setRoles] = useState<Record<string, string>>({});

  useEffect(() => {
    Promise.all([
      customersApi.list(),
      streamsApi.list(),
      usersApi.list(),
      projectsApi.list(),
      rolesApi.list(),
    ])
      .then(([customerRows, streamRows, userRows, projectRows, roleRows]) => {
        setCustomers(Object.fromEntries(customerRows.map((c) => [c.id, c.name])));
        setStreams(Object.fromEntries(streamRows.map((s) => [s.id, s.name])));
        setUsers(
          Object.fromEntries(
            userRows.map((u) => [u.id, `${u.first_name} ${u.last_name}`]),
          ),
        );
        setProjects(
          Object.fromEntries(projectRows.map((p) => [p.id, projectLabel(p)])),
        );
        setRoles(Object.fromEntries(roleRows.map((r) => [r.id, r.name])));
      })
      .catch(() => {
        // lookups are optional for display
      });
  }, []);

  return { customers, streams, users, projects, roles };
}
