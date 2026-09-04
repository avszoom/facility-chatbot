export const humanize = (value: string): string =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export const ticketStatusLabel = (status: string): string => {
  if (status === "waiting_technician") return "Ongoing · Technician";
  if (status === "waiting_verification") return "Ongoing · Verifying";
  return humanize(status);
};
