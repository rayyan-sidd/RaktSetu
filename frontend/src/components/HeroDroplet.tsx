import { useRef, useMemo, useEffect, useState } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import * as THREE from 'three'

interface DropletSceneProps {
  isDark: boolean
  reducedMotion: boolean
}

function DropletMesh({ isDark, reducedMotion }: DropletSceneProps) {
  const meshRef = useRef<THREE.Mesh>(null!)
  const innerRef = useRef<THREE.Mesh>(null!)
  const groupRef = useRef<THREE.Group>(null!)
  const orbitRef1 = useRef<THREE.Group>(null!)
  const orbitRef2 = useRef<THREE.Group>(null!)

  // Smooth, organic teardrop cross-section
  const geometry = useMemo(() => {
    const points: THREE.Vector2[] = []
    const segments = 64
    for (let i = 0; i <= segments; i++) {
      const u = i / segments // 0 to 1
      const theta = u * Math.PI // 0 at bottom, PI at top
      // Height mapping: rounded base at -1.65, apex at +1.85
      const y = -1.65 * Math.cos(theta) + 0.2 * Math.sin(theta)
      // Fluid teardrop profile: wide bottom, graceful concave taper to apex
      const profile = Math.sin(theta) * Math.pow(Math.cos(theta * 0.45), 1.6)
      const r = Math.max(0.001, profile * 1.55)
      points.push(new THREE.Vector2(r, y))
    }
    const geom = new THREE.LatheGeometry(points, 72)
    geom.computeVertexNormals()
    return geom
  }, [])

  // Inner core geometry for luminous optical depth
  const innerGeometry = useMemo(() => {
    const points: THREE.Vector2[] = []
    const segments = 32
    for (let i = 0; i <= segments; i++) {
      const u = i / segments
      const theta = u * Math.PI
      const y = (-1.5 * Math.cos(theta) + 0.2 * Math.sin(theta)) * 0.82
      const profile = Math.sin(theta) * Math.pow(Math.cos(theta * 0.45), 1.6)
      const r = Math.max(0.001, profile * 1.25)
      points.push(new THREE.Vector2(r, y))
    }
    const geom = new THREE.LatheGeometry(points, 48)
    geom.computeVertexNormals()
    return geom
  }, [])

  // Soft contact shadow texture generated dynamically
  const shadowTexture = useMemo(() => {
    const canvas = document.createElement('canvas')
    canvas.width = 128
    canvas.height = 128
    const ctx = canvas.getContext('2d')
    if (ctx) {
      const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 64)
      gradient.addColorStop(0, isDark ? 'rgba(0, 0, 0, 0.55)' : 'rgba(20, 36, 51, 0.20)')
      gradient.addColorStop(0.35, isDark ? 'rgba(0, 0, 0, 0.3)' : 'rgba(20, 36, 51, 0.10)')
      gradient.addColorStop(0.7, isDark ? 'rgba(0, 0, 0, 0.08)' : 'rgba(20, 36, 51, 0.03)')
      gradient.addColorStop(1, 'rgba(0, 0, 0, 0)')
      ctx.fillStyle = gradient
      ctx.fillRect(0, 0, 128, 128)
    }
    return new THREE.CanvasTexture(canvas)
  }, [isDark])

  // Luxurious, glossy ruby-glass material (no dark outlines, clean refraction)
  const rubyGlassMaterial = useMemo(() => {
    return new THREE.MeshPhysicalMaterial({
      color: new THREE.Color(isDark ? '#D92344' : '#B91C35'),
      emissive: new THREE.Color(isDark ? '#4A0813' : '#33050C'),
      roughness: 0.09,
      metalness: 0.0,
      clearcoat: 1.0,
      clearcoatRoughness: 0.05,
      transmission: 0.52,
      ior: 1.45,
      thickness: 1.4,
      attenuationColor: new THREE.Color('#FF2E51'),
      attenuationDistance: 1.6,
      specularIntensity: 1.0,
      specularColor: new THREE.Color('#FFFFFF'),
      transparent: true,
      opacity: 0.98,
    })
  }, [isDark])

  // Luminous internal fluid core
  const innerCoreMaterial = useMemo(() => {
    return new THREE.MeshBasicMaterial({
      color: new THREE.Color(isDark ? '#FF3355' : '#E11D48'),
      transparent: true,
      opacity: isDark ? 0.28 : 0.2,
    })
  }, [isDark])

  // Delicate orbital curves
  const orbitMaterial = useMemo(() => {
    return new THREE.MeshBasicMaterial({
      color: new THREE.Color(isDark ? '#94A3B8' : '#64748B'),
      transparent: true,
      opacity: isDark ? 0.25 : 0.3,
    })
  }, [isDark])

  const nodeMaterialRuby = useMemo(() => {
    return new THREE.MeshBasicMaterial({
      color: new THREE.Color('#B91C35'),
    })
  }, [])

  const nodeMaterialSlate = useMemo(() => {
    return new THREE.MeshBasicMaterial({
      color: new THREE.Color(isDark ? '#CBD5E1' : '#64748B'),
    })
  }, [isDark])

  // Restrained, slow floating & subtle rotation
  useFrame((state) => {
    if (reducedMotion) return

    const t = state.clock.getElapsedTime()

    // Smooth vertical float
    if (groupRef.current) {
      groupRef.current.position.y = Math.sin(t * 0.75) * 0.09
    }

    // Slow organic rotation
    if (meshRef.current) {
      meshRef.current.rotation.y = t * 0.18
      meshRef.current.rotation.z = Math.sin(t * 0.5) * 0.03
    }

    if (innerRef.current) {
      innerRef.current.rotation.y = -t * 0.1
    }

    // Gentle orbital curve tilt rotation
    if (orbitRef1.current) {
      orbitRef1.current.rotation.z = t * 0.12
    }
    if (orbitRef2.current) {
      orbitRef2.current.rotation.z = -t * 0.09
    }
  })

  return (
    <group ref={groupRef} position={[0, 0, 0]}>
      {/* Primary Sculptural Teardrop */}
      <mesh ref={meshRef} geometry={geometry} material={rubyGlassMaterial}>
        {/* Optical Core */}
        <mesh ref={innerRef} geometry={innerGeometry} material={innerCoreMaterial} />
      </mesh>

      {/* Refined Orbital Network Curve 1 */}
      <group ref={orbitRef1.current ? orbitRef1 : undefined} rotation={[1.15, 0.35, 0]}>
        <mesh material={orbitMaterial}>
          <torusGeometry args={[2.25, 0.009, 16, 128]} />
        </mesh>
        {/* Connected Node 1 (Ruby) */}
        <mesh position={[2.25, 0, 0]} material={nodeMaterialRuby}>
          <sphereGeometry args={[0.065, 16, 16]} />
        </mesh>
        {/* Connected Node 2 (Neutral Slate) */}
        <mesh position={[-2.25, 0, 0]} material={nodeMaterialSlate}>
          <sphereGeometry args={[0.055, 16, 16]} />
        </mesh>
      </group>

      {/* Refined Orbital Network Curve 2 */}
      <group ref={orbitRef2.current ? orbitRef2 : undefined} rotation={[-0.85, -0.5, 0.3]}>
        <mesh material={orbitMaterial}>
          <torusGeometry args={[2.65, 0.007, 16, 128]} />
        </mesh>
        {/* Connected Node 3 */}
        <mesh position={[0, 2.65, 0]} material={nodeMaterialSlate}>
          <sphereGeometry args={[0.055, 16, 16]} />
        </mesh>
        {/* Connected Node 4 */}
        <mesh position={[0, -2.65, 0]} material={nodeMaterialRuby}>
          <sphereGeometry args={[0.05, 16, 16]} />
        </mesh>
      </group>

      {/* Soft Contact Shadow Texture Disc */}
      <mesh position={[0, -2.15, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[3.6, 3.6]} />
        <meshBasicMaterial map={shadowTexture} transparent depthWrite={false} />
      </mesh>
    </group>
  )
}

// Graceful fallback during load or unsupported WebGL
export function DropletFallback() {
  return (
    <div className="w-full h-[360px] sm:h-[440px] lg:h-[480px] flex items-center justify-center">
      <div className="w-40 h-40 sm:w-48 sm:h-48 rounded-full bg-gradient-to-tr from-[#8C1024] via-[#B91C35] to-[#E11D48] shadow-xl shadow-[#B91C35]/25 flex items-center justify-center animate-pulse">
        <div className="w-14 h-16 bg-white/25 rounded-full blur-[2px]" />
      </div>
    </div>
  )
}

export default function HeroDroplet({ isDark = false }: { isDark?: boolean }) {
  const [reducedMotion, setReducedMotion] = useState(false)
  const [hasWebGL, setHasWebGL] = useState(true)

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const media = window.matchMedia('(prefers-reduced-motion: reduce)')
      setReducedMotion(media.matches)
      const listener = (e: MediaQueryListEvent) => setReducedMotion(e.matches)
      media.addEventListener('change', listener)
      return () => media.removeEventListener('change', listener)
    }
  }, [])

  useEffect(() => {
    try {
      const canvas = document.createElement('canvas')
      const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl')
      if (!gl) setHasWebGL(false)
    } catch {
      setHasWebGL(false)
    }
  }, [])

  if (!hasWebGL) {
    return <DropletFallback />
  }

  return (
    <div className="w-full h-[360px] sm:h-[440px] lg:h-[480px] relative flex items-center justify-center select-none pointer-events-none">
      {/* Refined Ambient Blush Radial Glow */}
      <div
        className="absolute inset-0 rounded-full pointer-events-none"
        style={{
          background: isDark
            ? 'radial-gradient(circle at center, rgba(185, 28, 53, 0.22) 0%, rgba(20, 36, 51, 0) 70%)'
            : 'radial-gradient(circle at center, rgba(255, 241, 242, 0.95) 0%, rgba(185, 28, 53, 0.08) 45%, rgba(255, 255, 255, 0) 72%)',
        }}
      />

      <Canvas
        camera={{ position: [0, 0.35, 6.4], fov: 40 }}
        dpr={[1, 2]}
        gl={{ antialias: true, alpha: true, powerPreference: 'high-performance' }}
      >
        {/* Balanced Studio Lighting Scheme */}
        <ambientLight intensity={isDark ? 0.75 : 0.9} color="#FFF1F2" />
        {/* Soft Key Light from top-left */}
        <directionalLight position={[-3.5, 4.5, 4.0]} intensity={isDark ? 1.6 : 1.9} color="#FFFFFF" />
        {/* Warm Fill Light from top-right */}
        <directionalLight position={[3.5, 2.0, 3.0]} intensity={0.8} color="#FFF1F2" />
        {/* Crimson Rim Light from bottom-rear for contoured edge glow */}
        <directionalLight position={[0, -2.8, -3.0]} intensity={isDark ? 2.4 : 1.6} color="#FF3355" />
        {/* Specular Glint */}
        <pointLight position={[-0.8, 2.5, 3.2]} intensity={0.7} color="#FFFFFF" />

        <DropletMesh isDark={isDark} reducedMotion={reducedMotion} />
      </Canvas>
    </div>
  )
}
