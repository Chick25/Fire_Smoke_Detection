import { useEffect, useRef } from "react";

export function useWebcam() {
  const videoRef =
    useRef<HTMLVideoElement>(null);

  useEffect(() => {
    let stream: MediaStream;

    const startCamera = async () => {
      try {
        stream =
          await navigator.mediaDevices.getUserMedia(
            {
              video: true
            }
          );

        if (videoRef.current) {
          videoRef.current.srcObject =
            stream;
        }
      } catch (err) {
        console.error(err);
      }
    };

    startCamera();

    return () => {
      stream
        ?.getTracks()
        .forEach((track) =>
          track.stop()
        );
    };
  }, []);

  return videoRef;
}