"use client";

import { useQuery } from "@tanstack/react-query";

import { api, ApiError } from "./api";
import type { Me } from "./types";

/** The signed-in user, or null. `undefined` while loading. */
export function useMe(): Me | null | undefined {
  const { data } = useQuery({
    queryKey: ["me"],
    queryFn: async () => {
      try {
        return await api<Me>("/auth/me");
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: 60_000,
  });
  return data;
}
