import React, { useRef } from "react";
import Navbar from "../components/Navbar";
import GuideSection from "../components/GuideSection";
import BusinessSection from "../components/BusinessSection";
import StartSection from "../components/StartSection";
import IntroSection from "../components/IntroSection";

const sectionStyle = {
  scrollSnapAlign: "start",
  width: "100%",
  minHeight: "100vh",
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  maxWidth: "100vw",
  boxSizing: "border-box",
};

export default function Home() {
  const introRef = useRef(null);
  const guideRef = useRef(null);
  const businessRef = useRef(null);

  const handleIntro = () => {
    introRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  const handleGuide = () => {
    guideRef.current?.scrollIntoView({ behavior: "smooth" });
  };
  
  const handleBusiness = () => {
    businessRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  return (
    <div
      className="home-container"
      style={{
        width: "100%",
        minHeight: "100vh",
        overflowX: "hidden",
        overflowY: "auto",
        scrollSnapType: "y mandatory",
        background: "#f8f8f8",
        position: "relative",
        paddingTop: 60,
        maxWidth: "100vw",
        boxSizing: "border-box",
      }}
    >
      <Navbar 
        onIntro={handleIntro} 
        onGuide={handleGuide} 
        onBusiness={handleBusiness} 
      />
      
      <section style={{ ...sectionStyle, background: "rgba(255,255,255,0.2)" }}>
        <StartSection />
      </section>
      
      <section 
        ref={introRef} 
        id="intro-section" 
        style={{ ...sectionStyle, background: "#fff" }}
      >
        <IntroSection />
      </section>
      
      <section 
        ref={guideRef} 
        id="guide-section" 
        style={{ ...sectionStyle, background: "#fff" }}
      >
        <GuideSection />
      </section>
      
      <section 
        ref={businessRef} 
        id="business-section" 
        style={{ 
          ...sectionStyle, 
          background: "#444", 
          color: "#fff", 
          minHeight: `25vh`, // 1/4 of viewport height
          height: `25vh` 
        }}
      >
        <BusinessSection />
      </section>
    </div>
  );
}
