"""
Wheel Generator - FIXED: Font handling with custom fonts folder
"""

from PIL import Image, ImageDraw, ImageFont
import math
import io
import logging
import os
from .random_service import RandomService

logger = logging.getLogger(__name__)

class WheelGenerator:

    @staticmethod
    def get_font(size: int = 20):
        """
        Lädt eine Font-Datei aus dem fonts/ Ordner oder fallback zu System-Fonts
        """
        try:
            # Pfad zum fonts/ Ordner (neben main.py)
            fonts_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'fonts')
            
            # Verschiedene Font-Dateien versuchen
            font_files = [
                'arial.ttf',
                'Arial.ttf', 
                'arial_bold.ttf',
                'helvetica.ttf',
                'Roboto-Regular.ttf',
                'OpenSans-Regular.ttf'
            ]
            
            # Versuche Font aus fonts/ Ordner zu laden
            for font_file in font_files:
                font_path = os.path.join(fonts_dir, font_file)
                if os.path.exists(font_path):
                    try:
                        font = ImageFont.truetype(font_path, size)
                        logger.debug(f"✅ Font loaded: {font_file} (Size: {size})")
                        return font
                    except Exception as e:
                        logger.warning(f"Could not load {font_file}: {e}")
                        continue
            
            logger.warning(f"No custom fonts found in {fonts_dir}")
            
        except Exception as e:
            logger.warning(f"Error accessing fonts directory: {e}")
        
        # Fallback zu System-Fonts
        try:
            # Windows
            font = ImageFont.truetype("arial.ttf", size)
            logger.debug(f"✅ System font loaded: arial.ttf (Size: {size})")
            return font
        except:
            try:
                # macOS
                font = ImageFont.truetype("/System/Library/Fonts/Arial.ttf", size)
                logger.debug(f"✅ System font loaded: macOS Arial (Size: {size})")
                return font
            except:
                try:
                    # Linux - verschiedene Pfade versuchen
                    linux_fonts = [
                        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
                        "/usr/share/fonts/TTF/arial.ttf",
                        "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
                    ]
                    
                    for font_path in linux_fonts:
                        if os.path.exists(font_path):
                            try:
                                font = ImageFont.truetype(font_path, size)
                                logger.debug(f"✅ Linux system font loaded: {os.path.basename(font_path)} (Size: {size})")
                                return font
                            except:
                                continue
                    
                    logger.warning("No Linux system fonts found, using default")
                    
                except:
                    pass
                
                # Letzter Fallback - Default Font (aber mit Warnung)
                logger.warning(f"Using default font - text may be small! Size parameter {size} ignored.")
                return ImageFont.load_default()

    @staticmethod
    def create_wheel_frame(options: list, rotation_angle: float = 0, show_winner: bool = False, selected_option: str = None) -> Image.Image:
        size = 600
        center = size // 2
        radius = 250
        
        img = Image.new('RGB', (size, size), '#1a1a1a')
        draw = ImageDraw.Draw(img)
        
        # FIXED: Größere Font mit verbessertem Handling
        font = WheelGenerator.get_font(16)  # Größere Schrift für bessere Lesbarkeit
        
        colors = [
            '#2C3E50',
            '#8B0000',
            '#34495E',
            '#722F37',
            '#1B2631',
            '#A93226',
            '#273746',
            '#6C3483'
        ]
        
        num_options = len(options)
        angle_per_option = 360 / num_options
        
        selected_index = -1
        if show_winner and selected_option:
            try:
                selected_index = options.index(selected_option)
            except ValueError:
                pass
        
        # Wheel Segmente zeichnen
        for i, option in enumerate(options):
            start_angle = i * angle_per_option + rotation_angle
            end_angle = (i + 1) * angle_per_option + rotation_angle
            
            color = colors[i % len(colors)]
            
            if show_winner and i == selected_index:
                color = '#DC143C'  # Highlight für Gewinner
            
            draw.pieslice([center-radius, center-radius, center+radius, center+radius], 
                         start_angle, end_angle, fill=color, outline='#FFFFFF', width=3)
        
        # Text auf Segmente
        for i, option in enumerate(options):
            text_angle_deg = i * angle_per_option + angle_per_option / 2 + rotation_angle
            text_angle_rad = math.radians(text_angle_deg)
            
            text_radius = radius * 0.6
            text_x = center + text_radius * math.cos(text_angle_rad)
            text_y = center + text_radius * math.sin(text_angle_rad)
            
            # FIXED: Größere Text-Area für bessere Lesbarkeit
            text_img = Image.new('RGBA', (300, 80), (0, 0, 0, 0))
            text_draw = ImageDraw.Draw(text_img)
            
            # FIXED: Stärkerer Stroke für bessere Lesbarkeit
            text_draw.text((150, 40), str(option), fill='#FFFFFF', font=font, 
                          stroke_width=3, stroke_fill='#000000', anchor='mm')
            
            rotated_text = text_img.rotate(-text_angle_deg, expand=True)
            
            text_w, text_h = rotated_text.size
            paste_x = int(text_x - text_w // 2)
            paste_y = int(text_y - text_h // 2)
            
            img.paste(rotated_text, (paste_x, paste_y), rotated_text)
        
        # Wheel Border
        draw.ellipse([center-radius-5, center-radius-5, center+radius+5, center+radius+5], 
                     outline='#FFFFFF', width=8)
        
        # Pointer/Arrow
        draw.polygon([(center, center-radius-15), (center-20, center-radius-40), 
                      (center+20, center-radius-40)], fill='#FFFFFF', outline='#000000', width=2)
        
        # Center Circle
        draw.ellipse([center-25, center-25, center+25, center+25], fill='#FFFFFF', outline='#000000', width=3)
        draw.ellipse([center-15, center-15, center+15, center+15], fill='#1a1a1a')
        
        return img
    
    @staticmethod
    async def create_spinning_wheel_gif(options: list, selected_option: str) -> io.BytesIO:
        frames = []
        
        try:
            selected_index = options.index(selected_option)
        except ValueError:
            logger.error(f"Selected option '{selected_option}' not found in options")
            selected_index = 0
            
        angle_per_option = 360 / len(options)
        
        # True Random Zahlen von random.org
        random_numbers = await RandomService.get_true_random_numbers(3, 0, 1000)
        
        # Random Offset innerhalb des Segments
        random_offset_factor = (random_numbers[0] / 1000) * 0.6 - 0.3
        random_offset = random_offset_factor * angle_per_option
        
        # Random Anzahl zusätzlicher Umdrehungen
        rotation_count = 4 + (random_numbers[1] % 4)
        
        logger.info(f"🎲 True Random parameters: Selected={selected_option} (Index {selected_index}), Offset={random_offset:.1f}°, Rotations={rotation_count}")
        
        # Berechne finalen Winkel
        target_segment_angle = selected_index * angle_per_option + angle_per_option / 2
        final_angle = 270 - target_segment_angle + random_offset
        
        total_rotation = 360 * rotation_count + final_angle
        
        logger.info(f"🎯 Final calculation: Segment at {target_segment_angle:.1f}°, Final position {final_angle:.1f}°, Total {total_rotation:.1f}°")
        
        # Spin Animation
        spin_frames = 80
        for i in range(spin_frames):
            progress = i / spin_frames
            # Ease-out Animation
            eased_progress = 1 - (1 - progress) ** 2
            
            current_angle = total_rotation * eased_progress
            frame = WheelGenerator.create_wheel_frame(options, current_angle)
            frames.append(frame)
        
        # Result Frames (Winner highlight)
        for i in range(20):
            frame = WheelGenerator.create_wheel_frame(options, final_angle, show_winner=True, selected_option=selected_option)
            frames.append(frame)
        
        # GIF erstellen
        gif_buffer = io.BytesIO()
        frames[0].save(
            gif_buffer, 
            format='GIF',
            save_all=True,
            append_images=frames[1:],
            duration=[40] * spin_frames + [100] * 20,  # Schnelle Animation + längere Anzeige
            loop=0
        )
        gif_buffer.seek(0)
        
        return gif_buffer