import { useEffect } from "react";
import { useProperties } from "../api/useProperties";
import { usePropertyStore } from "../stores/useProperty";

export function PropertySelector() {
  const { data, isLoading } = useProperties();
  const propertyId = usePropertyStore((state) => state.propertyId);
  const setPropertyId = usePropertyStore((state) => state.setPropertyId);

  useEffect(() => {
    if (!propertyId && data?.length) {
      setPropertyId(data[0].property_id);
    }
  }, [data, propertyId, setPropertyId]);

  return (
    <label className="flex items-center gap-3 text-xs font-medium uppercase tracking-[0.16em] text-muted">
      <span>Property</span>
      <select
        value={propertyId ?? ""}
        onChange={(event) => setPropertyId(Number(event.target.value))}
        className="input min-w-56 normal-case tracking-normal"
        disabled={isLoading}
      >
        <option value="" disabled>
          Select property
        </option>
        {data?.map((property) => (
          <option key={property.property_id} value={property.property_id}>
            {property.property_name ?? property.name ?? `Property ${property.property_id}`}
          </option>
        ))}
      </select>
    </label>
  );
}
