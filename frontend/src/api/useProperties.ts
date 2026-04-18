import { useQuery } from "@tanstack/react-query";
import { api } from "./client";

export type Property = {
  property_id: number;
  property_name?: string;
  name?: string;
};

async function fetchProperties(): Promise<Property[]> {
  const { data } = await api.get<Property[]>("/properties");
  return data;
}

export function useProperties() {
  return useQuery({
    queryKey: ["properties"],
    queryFn: fetchProperties,
  });
}
