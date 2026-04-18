import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

type PropertyState = {
  propertyId: number | null;
  setPropertyId: (propertyId: number | null) => void;
};

export const usePropertyStore = create<PropertyState>()(
  persist(
    (set) => ({
      propertyId: null,
      setPropertyId: (propertyId) => set({ propertyId }),
    }),
    {
      name: "dmrb-property",
      storage: createJSONStorage(() => localStorage),
    },
  ),
);
