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
  { number: 10, name: "Penthouses & Sky Lounge", use: "Penthouses and shared amenity", occupancy: 28, capacity: 44, area: "16,800 sq ft", status: "Normal", openTickets: 0, rooms: ["Apartments 1001–1006", "Sky lounge", "Roof terrace", "Mechanical 10"] },
  { number: 9, name: "Residences 901–918", use: "Residential apartments", occupancy: 43, capacity: 72, area: "17,200 sq ft", status: "Normal", openTickets: 0, rooms: ["Apartments 901–906", "Apartments 907–912", "Apartments 913–918", "Refuse room"] },
  { number: 8, name: "Residences 801–818", use: "Residential apartments", occupancy: 51, capacity: 72, area: "18,400 sq ft", status: "Normal", openTickets: 0, rooms: ["Apartments 801–806", "Apartments 807–812", "Apartments 813–818", "Laundry room"] },
  { number: 7, name: "Residences 701–718", use: "Residential apartments", occupancy: 47, capacity: 72, area: "18,400 sq ft", status: "Normal", openTickets: 0, rooms: ["East residential wing", "West residential wing", "Electrical 7A", "Refuse room"] },
  { number: 6, name: "Residences 601–618", use: "Residential apartments", occupancy: 55, capacity: 72, area: "18,400 sq ft", status: "Normal", openTickets: 0, rooms: ["Apartments 601–606", "Apartments 607–612", "Apartments 613–618", "Laundry room"] },
  { number: 5, name: "Residences 501–518", use: "Residential apartments", occupancy: 49, capacity: 72, area: "18,400 sq ft", status: "Normal", openTickets: 0, rooms: ["Apartment 5E", "East residential wing", "Resident lounge", "Refuse room"] },
  { number: 4, name: "Residences 401–418", use: "Residential apartments", occupancy: 38, capacity: 72, area: "18,100 sq ft", status: "Normal", openTickets: 0, rooms: ["Apartment 4B", "East residential wing", "West residential wing", "Laundry room"] },
  { number: 3, name: "Residences 301–318", use: "Residential apartments", occupancy: 45, capacity: 72, area: "18,100 sq ft", status: "Normal", openTickets: 0, rooms: ["Apartments 301–306", "Apartments 307–312", "Apartments 313–318", "Refuse room"] },
  { number: 2, name: "Fitness & Residents Club", use: "Resident amenities", occupancy: 31, capacity: 90, area: "17,700 sq ft", status: "Normal", openTickets: 0, rooms: ["Fitness center", "Yoga studio", "Resident lounge", "Indoor pool"] },
  { number: 1, name: "Lobby, Café & Services", use: "Resident services and retail", occupancy: 36, capacity: 100, area: "22,500 sq ft", status: "Normal", openTickets: 0, rooms: ["Main lobby", "Northstar Café", "Parcel room", "Management office"] },
];

const baseSensors = (floor: FloorRecord): SensorRecord[] => {
  const pad = String(floor.number).padStart(2, "0");
  const temperature = floor.number === 4 ? "72.7°F" : `${(69.8 + (floor.number % 4) * 0.7).toFixed(1)}°F`;
  const temperatureState: SensorState = "Normal";
  return [
    { id: `TMP-${pad}-01`, floor: floor.number, area: floor.name, type: "Temperature", value: temperature, target: "68–75°F", state: temperatureState, seen: `${4 + floor.number}s ago` },
    { id: `AIR-${pad}-01`, floor: floor.number, area: floor.name, type: "CO₂", value: `${450 + floor.number * 31} ppm`, target: "< 1,000 ppm", state: "Normal", seen: `${8 + floor.number}s ago` },
    { id: `HUM-${pad}-01`, floor: floor.number, area: floor.name, type: "Humidity", value: `${39 + (floor.number % 5)}%`, target: "30–60%", state: "Normal", seen: `${11 + floor.number}s ago` },
    { id: `VOC-${pad}-01`, floor: floor.number, area: floor.name, type: "VOC / odor", value: `${16 + floor.number} ppb`, target: "< 50 ppb", state: "Normal", seen: `${7 + floor.number}s ago` },
    { id: `OCC-${pad}-01`, floor: floor.number, area: floor.name, type: "Occupancy", value: `${floor.occupancy} people`, target: `≤ ${floor.capacity}`, state: "Normal", seen: `${5 + floor.number}s ago` },
    { id: `PWR-${pad}-01`, floor: floor.number, area: floor.name, type: "Electrical load", value: `${46 + floor.number * 3} kW`, target: "< 110 kW", state: "Normal", seen: `${3 + floor.number}s ago` },
  ];
};

export const sensors: SensorRecord[] = floors.flatMap(baseSensors).map((sensor) => sensor.id === "PWR-07-01" ? { ...sensor, id: "ELEC-7A", area: "Floor 7 east residential wing", type: "Cabinet temperature", value: "84.2°F", target: "< 95°F" } : sensor);

export const totalOccupancy = floors.reduce((sum, floor) => sum + floor.occupancy, 0);
export const totalCapacity = floors.reduce((sum, floor) => sum + floor.capacity, 0);
