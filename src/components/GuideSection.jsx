import React from "react";
import "./GuideSection.css";

export default function GuideSection() {
  return (
    <div className="guide-section">
      <h3 className="guide-title">가이드</h3>
      <div className="guide-row">
        <div className="guide-col guide-col1">
          <div className="guide-box guide-box1"></div>
          <small>간단가이드</small>
        </div>
        <div className="guide-col guide-col2"></div>
      </div>
      <div className="guide-bottom-box">
        <button className="guide-play-btn">재생</button>
      </div>
    </div>
  );
}
