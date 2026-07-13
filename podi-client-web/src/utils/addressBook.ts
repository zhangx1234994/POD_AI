import type { ClientShippingAddress } from "../types";

const ADDRESS_STORAGE_KEY = "podi-client-web.default-shipping-address.v1";

export const emptyShippingAddress: ClientShippingAddress = {
  recipientName: "",
  phoneNumber: "",
  country: "CN",
  state: "",
  city: "",
  district: "",
  postalCode: "",
  address: "",
  email: "",
};

function normalizeAddress(value: Partial<ClientShippingAddress> | null | undefined): ClientShippingAddress {
  return {
    recipientName: value?.recipientName?.trim() ?? "",
    phoneNumber: value?.phoneNumber?.trim() ?? "",
    country: (value?.country?.trim() || "CN").toUpperCase(),
    state: value?.state?.trim() ?? "",
    city: value?.city?.trim() ?? "",
    district: value?.district?.trim() ?? "",
    postalCode: value?.postalCode?.trim() ?? "",
    address: value?.address?.trim() ?? "",
    email: value?.email?.trim() ?? "",
  };
}

export function readStoredAddress(): ClientShippingAddress {
  if (typeof window === "undefined") return emptyShippingAddress;
  try {
    const raw = window.localStorage.getItem(ADDRESS_STORAGE_KEY);
    if (!raw) return emptyShippingAddress;
    return normalizeAddress(JSON.parse(raw) as Partial<ClientShippingAddress>);
  } catch {
    return emptyShippingAddress;
  }
}

export function writeStoredAddress(address: ClientShippingAddress): ClientShippingAddress {
  const normalized = normalizeAddress(address);
  if (typeof window !== "undefined") {
    window.localStorage.setItem(ADDRESS_STORAGE_KEY, JSON.stringify(normalized));
  }
  return normalized;
}
