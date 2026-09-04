import { Canvas } from "@react-three/fiber";
import { ContactShadows, Grid, OrbitControls, RoundedBox } from "@react-three/drei";
import type { ThreeEvent } from "@react-three/fiber";
import type { FloorRecord } from "./facility";

function Tower({ floors, selectedFloor, onSelect }: { floors: FloorRecord[]; selectedFloor: number; onSelect: (floor: number) => void }) {
  const ordered = [...floors].sort((a, b) => a.number - b.number);
  return <group position={[0, -2.65, 0]} rotation={[0, -0.32, 0]}>
    {ordered.map((floor, index) => {
      const selected = floor.number === selectedFloor;
      const alert = floor.status === "Critical";
      const y = index * .56;
      const click = (event: ThreeEvent<MouseEvent>) => { event.stopPropagation(); onSelect(floor.number); };
      return <group key={floor.number} position={[0, y, 0]} onClick={click}>
        <RoundedBox args={[4.5, .48, 3.05]} radius={.06} smoothness={3} castShadow receiveShadow>
          <meshStandardMaterial color={selected ? "#1da1f2" : alert ? "#b5343e" : "#162333"} emissive={selected ? "#0569a6" : alert ? "#5b0b12" : "#06101a"} emissiveIntensity={selected ? .85 : .32} metalness={.62} roughness={.24} transparent opacity={selected ? .98 : .92} />
        </RoundedBox>
        {[-1.65, -1.08, -.51, .06, .63, 1.2, 1.77].map((x) => <mesh key={`front-${x}`} position={[x, .02, 1.53]}>
          <boxGeometry args={[.36, .24, .025]} />
          <meshStandardMaterial color={selected ? "#c8f2ff" : alert ? "#ffad95" : "#4f7896"} emissive={selected ? "#2fb9ff" : alert ? "#d74232" : "#163c5a"} emissiveIntensity={.7} />
        </mesh>)}
        {[-1.12, -.56, 0, .56, 1.12].map((z) => <mesh key={`side-${z}`} position={[2.26, .02, z]} rotation={[0, Math.PI / 2, 0]}>
          <boxGeometry args={[.34, .24, .025]} />
          <meshStandardMaterial color={selected ? "#c8f2ff" : "#365d79"} emissive={selected ? "#2fb9ff" : "#102c42"} emissiveIntensity={.55} />
        </mesh>)}
        <mesh position={[-2.3, .03, 0]}><boxGeometry args={[.05, .3, 2.72]} /><meshStandardMaterial color={selected ? "#60c8ff" : "#223a51"} /></mesh>
      </group>;
    })}
    <RoundedBox args={[4.8, .22, 3.35]} radius={.08} position={[0, -.34, 0]} receiveShadow><meshStandardMaterial color="#0a111a" metalness={.5} /></RoundedBox>
    <RoundedBox args={[2.0, .52, 1.4]} radius={.08} position={[.4, 5.42, 0]} castShadow><meshStandardMaterial color="#172333" metalness={.75} roughness={.3} /></RoundedBox>
    <mesh position={[.4, 6.05, 0]}><cylinderGeometry args={[.035, .035, .85, 12]} /><meshStandardMaterial color="#62c7ff" emissive="#1c82bb" emissiveIntensity={.8} /></mesh>
  </group>;
}

export function BuildingScene({ floors, selectedFloor, onSelect }: { floors: FloorRecord[]; selectedFloor: number; onSelect: (floor: number) => void }) {
  return <Canvas shadows camera={{ position: [8.4, 5.5, 10.5], fov: 35 }} dpr={[1, 1.75]}>
    <color attach="background" args={["#05080d"]} />
    <fog attach="fog" args={["#05080d", 15, 27]} />
    <ambientLight intensity={.7} />
    <directionalLight position={[5, 10, 7]} intensity={2.3} color="#d4ecff" castShadow />
    <pointLight position={[-6, 4, 3]} intensity={15} color="#1769e0" distance={15} />
    <pointLight position={[6, 1, -4]} intensity={10} color="#1fd9bd" distance={13} />
    <Tower floors={floors} selectedFloor={selectedFloor} onSelect={onSelect} />
    <Grid position={[0, -3.05, 0]} args={[22, 22]} cellSize={.6} cellThickness={.45} cellColor="#17314a" sectionSize={3} sectionThickness={.8} sectionColor="#245278" fadeDistance={18} fadeStrength={1.5} infiniteGrid />
    <ContactShadows position={[0, -3, 0]} opacity={.7} scale={14} blur={2.2} far={8} />
    <OrbitControls makeDefault enablePan={false} minDistance={8} maxDistance={19} minPolarAngle={Math.PI / 4.8} maxPolarAngle={Math.PI / 2.15} target={[0, -.1, 0]} />
  </Canvas>;
}
