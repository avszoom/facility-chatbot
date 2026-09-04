export type SensorState = "Normal" | "Warning" | "Critical";

export type FloorRecord = {
  number: number;
  name: string;
  use: string;
  occupancy: number;
  capacity: number;
  area: string;
  status: SensorState;
  openTickets: number;
  rooms: string[];
};

export type SensorRecord = {
  id: string;
  floor: number;
  area: string;
  type: string;
  value: string;
  target: string;
  state: SensorState;
  seen: string;
};

export const floors: FloorRecord[] = [
  { number: 10, name: "Executive & Board", use: "Executive offices", occupancy: 27, capacity: 42, area: "16,800 sq ft", status: "Normal", openTickets: 0, rooms: ["Boardroom", "Executive lounge", "Offices", "Focus rooms"] },
  { number: 9, name: "Finance & Legal", use: "Private offices", occupancy: 39, capacity: 58, area: "17,200 sq ft", status: "Normal", openTickets: 0, rooms: ["Finance east", "Legal west", "Meeting 9A", "Archive"] },
  { number: 8, name: "Product Studio", use: "Open workplace", occupancy: 51, capacity: 68, area: "18,400 sq ft", status: "Normal", openTickets: 0, rooms: ["Product studio", "Research lab", "Meeting 8B", "Pantry"] },
  { number: 7, name: "Engineering East", use: "Open workplace", occupancy: 46, capacity: 62, area: "18,400 sq ft", status: "Normal", openTickets: 0, rooms: ["East office zone", "Engineering west", "Electrical 7A", "Meeting 7C"] },
  { number: 6, name: "Engineering West", use: "Open workplace", occupancy: 54, capacity: 70, area: "18,400 sq ft", status: "Normal", openTickets: 0, rooms: ["Platform team", "Data team", "Lab 6A", "Pantry"] },
  { number: 5, name: "Product & Design", use: "Hybrid workplace", occupancy: 43, capacity: 64, area: "18,400 sq ft", status: "Normal", openTickets: 0, rooms: ["Design studio", "Product east", "Workshop", "Meeting 5D"] },
  { number: 4, name: "Client Services", use: "Meeting center", occupancy: 34, capacity: 56, area: "18,100 sq ft", status: "Normal", openTickets: 0, rooms: ["Conference 4B", "Client lounge", "Meeting 4A", "Support hub"] },
  { number: 3, name: "Sales & Marketing", use: "Open workplace", occupancy: 42, capacity: 66, area: "18,100 sq ft", status: "Normal", openTickets: 0, rooms: ["Sales floor", "Content studio", "Meeting 3C", "Pantry"] },
  { number: 2, name: "People & Operations", use: "Workplace services", occupancy: 31, capacity: 52, area: "17,700 sq ft", status: "Normal", openTickets: 0, rooms: ["People team", "Facilities", "Wellness room", "Training room"] },
  { number: 1, name: "Welcome & Amenities", use: "Public amenities", occupancy: 41, capacity: 80, area: "22,500 sq ft", status: "Normal", openTickets: 0, rooms: ["Main lobby", "Fitness center", "Café", "Security desk"] },
];

const baseSensors = (floor: FloorRecord): SensorRecord[] => {
  const pad = String(floor.number).padStart(2, "0");
  const temperature = floor.number === 4 ? "72.7°F" : `${(69.8 + (floor.number % 4) * 0.7).toFixed(1)}°F`;
  const temperatureState: SensorState = "Normal";
  return [
    { id: `TMP-${pad}-01`, floor: floor.number, area: floor.name, type: "Temperature", value: temperature, target: "68–75°F", state: temperatureState, seen: `${4 + floor.number}s ago` },
    { id: `AIR-${pad}-01`, floor: floor.number, area: floor.name, type: "CO₂", value: `${450 + floor.number * 31} ppm`, target: "< 1,000 ppm", state: "Normal", seen: `${8 + floor.number}s ago` },
    { id: `HUM-${pad}-01`, floor: floor.number, area: floor.name, type: "Humidity", value: `${39 + (floor.number % 5)}%`, target: "30–60%", state: "Normal", seen: `${11 + floor.number}s ago` },
    { id: `OCC-${pad}-01`, floor: floor.number, area: floor.name, type: "Occupancy", value: `${floor.occupancy} people`, target: `≤ ${floor.capacity}`, state: "Normal", seen: `${5 + floor.number}s ago` },
    { id: `PWR-${pad}-01`, floor: floor.number, area: floor.name, type: "Electrical load", value: `${78 + floor.number * 4} kW`, target: "< 145 kW", state: "Normal", seen: `${3 + floor.number}s ago` },
  ];
};

export const sensors: SensorRecord[] = floors.flatMap(baseSensors).map((sensor) => sensor.id === "PWR-07-01" ? { ...sensor, id: "ELEC-7A", area: "Floor 7 east panel", type: "Cabinet temperature", value: "84.2°F", target: "< 95°F" } : sensor);

export const totalOccupancy = floors.reduce((sum, floor) => sum + floor.occupancy, 0);
export const totalCapacity = floors.reduce((sum, floor) => sum + floor.capacity, 0);
